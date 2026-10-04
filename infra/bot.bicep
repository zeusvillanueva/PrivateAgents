targetScope = 'resourceGroup'

param botName string
param displayName string = 'Private Agent'

@description('Foundry agent instance_identity.client_id, not its principal_id.')
param agentClientId string

param tenantId string = tenant().tenantId

@description('Project endpoint followed by /agents/<name>/endpoint/protocols/activityProtocol?api-version=2025-05-15-preview')
param activityEndpoint string

resource bot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: botName
  location: 'global'
  kind: 'azurebot'
  sku: { name: 'F0' }
  properties: {
    displayName: displayName
    endpoint: activityEndpoint
    msaAppId: agentClientId
    msaAppTenantId: tenantId
    msaAppType: 'SingleTenant'
    publicNetworkAccess: 'Disabled'
  }
}

resource teams 'Microsoft.BotService/botServices/channels@2021-03-01' = {
  parent: bot
  name: 'MsTeamsChannel'
  location: 'global'
  properties: {
    channelName: 'MsTeamsChannel'
  }
}

output botServiceArmId string = bot.id
