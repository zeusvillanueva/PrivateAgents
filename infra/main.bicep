targetScope = 'resourceGroup'

param location string = resourceGroup().location

@minLength(2)
@maxLength(20)
@description('Lowercase alphanumeric prefix for globally unique account and registry names.')
param namePrefix string = 'privateagents'

param projectName string = 'private-agents'
param modelName string = 'gpt-4.1'
param modelVersion string = '2025-04-14'

@description('Choose a regional SKU for regional processing; verify model availability and quota.')
param modelSkuName string = 'Standard'

@minValue(1)
param modelCapacity int = 10

@description('Nonoverlapping RFC1918 network ranges; agent subnet must be /24 or larger.')
param vnetAddressPrefix string = '192.168.0.0/16'
param agentSubnetPrefix string = '192.168.0.0/24'
param endpointSubnetPrefix string = '192.168.1.0/24'

var suffix = uniqueString(resourceGroup().id)
var accountName = '${namePrefix}${suffix}'
var registryName = '${namePrefix}acr${suffix}'
var dnsZoneNames = [
  'privatelink.services.ai.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.cognitiveservices.azure.com'
  'privatelink.azurecr.io'
]

resource outboundIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${namePrefix}-egress'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource nat 'Microsoft.Network/natGateways@2024-05-01' = {
  name: '${namePrefix}-egress'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIpAddresses: [
      { id: outboundIp.id }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${namePrefix}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'agents'
        properties: {
          addressPrefix: agentSubnetPrefix
          defaultOutboundAccess: false
          natGateway: { id: nat.id }
          delegations: [
            {
              name: 'hosted-agents'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: endpointSubnetPrefix
          defaultOutboundAccess: false
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
    networkInjections: [
      {
        scenario: 'agent'
        subnetArmId: '${vnet.id}/subnets/agents'
        useMicrosoftManagedNetwork: false
      }
    ]
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: { name: 'Premium' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Disabled'
    networkRuleBypassOptions: 'None'
    networkRuleSet: {
      defaultAction: 'Deny'
      ipRules: []
    }
  }
}

resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zoneName in dnsZoneNames: {
  name: zoneName
  location: 'global'
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zoneName, i) in dnsZoneNames: {
  parent: zones[i]
  name: '${namePrefix}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: vnet.id }
  }
}]

resource endpoints 'Microsoft.Network/privateEndpoints@2024-05-01' = [for (service, i) in [
  { name: 'foundry', id: account.id, group: 'account' }
  { name: 'registry', id: registry.id, group: 'registry' }
]: {
  name: '${namePrefix}-${service.name}-pe'
  location: location
  properties: {
    subnet: { id: '${vnet.id}/subnets/private-endpoints' }
    privateLinkServiceConnections: [
      {
        name: service.name
        properties: {
          privateLinkServiceId: service.id
          groupIds: [service.group]
        }
      }
    ]
  }
}]

resource foundryZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: endpoints[0]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      for j in range(0, 3): {
        name: 'foundry-${j}'
        properties: { privateDnsZoneId: zones[j].id }
      }
    ]
  }
}

resource registryZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: endpoints[1]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'registry'
        properties: { privateDnsZoneId: zones[3].id }
      }
    ]
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Private Agents'
    description: 'Private hosted agents for Teams and Microsoft 365 Copilot.'
  }
}

resource capabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  parent: project
  name: 'agents'
  properties: {
    // The preview API supports this property; Bicep's published schema omits it.
    #disable-next-line BCP037
    capabilityHostKind: 'Agents'
  }
  dependsOn: [
    foundryZoneGroup
    registryZoneGroup
  ]
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: account
  name: modelName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource imagePull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, project.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${project.name}'
output projectId string = project.id
output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output modelDeploymentName string = model.name
output virtualNetworkId string = vnet.id
