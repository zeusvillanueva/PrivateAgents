# SharePoint agent

`sharepoint-agent` asks for a SharePoint site URL, checks that the **signed-in user** can access it (and at what permission level), rewrites the question into a SharePoint keyword query, searches the site, and answers from the top 10 results.

It never uses an app-only identity: every Graph/SharePoint call uses the user's delegated token, so results respect that user's permissions.

## How it works
1. The agent asks for the site URL (`https://<tenant>.sharepoint.com/sites/<name>`) if it has none.
2. `check_site_access` (`shared/sharepoint.py`): Graph `GET /sites/{host}:{path}` for access; SharePoint REST `/_api/web/effectiveBasePermissions` for the level (Full Control, Design/Manage, Edit, Contribute, Read). Without `sharepoint_token` it reports access only.
3. The model rewrites the question into 2-6 keywords (synonyms with `OR`, optional `filetype:`).
4. `search_sharepoint`: Graph `POST /search/query` (`driveItem`, scoped with `path:"<site>"`, size 10), then downloads each hit and extracts text: pages (`.aspx`), Word, PowerPoint, PDF (first 30 pages), text/CSV, Excel (first 50 rows per sheet). Legacy formats (`.doc`, `.ppt`, `.xls`, ...) are converted to PDF by Graph. Max 10 MB per file, 6000 characters of text each.
5. The agent answers from the results plus the original question and cites file URLs. The code interpreter is attached for calculations on spreadsheet previews.

Not covered: SharePoint list items without a file, files over 10 MB (summary only), unsupported file types (summary only).

## Prerequisites

### Entra app registration (the chat app's sign-in app)
1. **API permissions -> Microsoft Graph -> Delegated:** `Sites.Read.All`, `Files.Read.All`, `offline_access` (plus the existing `User.Read`, `openid`, `profile`, `email`).
2. *(Optional, for the permission level)* **SharePoint -> Delegated:** `AllSites.Read`.
3. **Grant admin consent** and confirm every row shows "Granted for <tenant>".
4. Reuse the existing client secret (no new credential needed). Its **Web** redirect URI is `<NEXTAUTH_URL>/api/auth/callback/azure-ad`.

### Chat app (`../PIAIAgentsChatApp`)
- Sign-in requests `offline_access Sites.Read.All Files.Read.All` and keeps the refresh token in the encrypted session JWT (`src/features/auth-page/auth-api.ts`).
- `src/app/api/agent/sharepointAuth.ts` exchanges the refresh token (existing client secret) for a Graph token, and a SharePoint token if `SHAREPOINT_HOSTNAME` is set, and prepends `<sharepoint_auth>{...}</sharepoint_auth>` to the message when the agent is `sharepoint-agent`. Tokens are minted per request and never stored.
- App settings: `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`, `AZURE_AD_TENANT_ID`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL` (must start with `https://` in Azure so the session cookie is found behind the proxy), optional `SHAREPOINT_HOSTNAME=<tenant>.sharepoint.com`.
- Register the agent in the Cosmos `agents` container with the exact name `sharepoint-agent` and the description from `scripts/register_agents.py`.

### This repo
- Deploy only this agent: run the `build-agents` workflow manually with `all=false` and `sharepoint=true` (a push to `main` deploys every agent).
- No new Azure resources, no storage, no extra env vars on the agent.

## Post-deploy checklist
1. Users **sign out and sign in again** (old sessions have no refresh token); they will see a consent prompt for the new permissions.
2. Chat with `sharepoint-agent` **directly**. The orchestrator path does not add the token block.
3. Test a site the user can access (expect site, permission level, search answer) and one they cannot (expect a clear "no access" reason).
4. Use the Azure sign-in, not the dev login (it has no tokens).

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| "missing user delegated token" | No `<sharepoint_auth>` block reached the agent. Check the chat app log stream for `[sharepoint:auth]`: |
| `session cookie not found` | `NEXTAUTH_URL` is not `https://...`, or `NEXTAUTH_SECRET` changed. Fix and sign in again. |
| `no refresh token in session` | Sign in again; confirm `offline_access` is granted with admin consent. |
| `token exchange failed 400 ... AADSTS65001` | Consent missing: grant admin consent for the Graph scopes. |
| `token exchange failed 400/401 ... invalid_client` | Client secret wrong or expired. |
| No `[sharepoint:auth]` log line | The agent name is not exactly `sharepoint-agent`, or the old chat app build is deployed. |
| Access granted but "Unknown (SharePoint token not provided)" | `SHAREPOINT_HOSTNAME` unset, or `AllSites.Read` not granted. Access still works. |
| `has_access: false`, HTTP 403/404 | User lacks access, or the URL is wrong. |
| Empty results | Search index delay for new content, or keywords too narrow; the agent retries once with broader terms. |

## Security notes
- Tokens are delegated, short-lived, validated and stripped by `SharePointAuthMiddleware` before the model sees them, and are never logged or returned.
- Only `https://*.sharepoint.com` URLs are accepted.
- File content is treated as data, not instructions.
