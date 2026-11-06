"""SharePoint tools: access check, permission level and content search (Microsoft Graph + SharePoint REST).

Everything runs as the signed-in user so results respect their permissions. The chat app obtains the user's
delegated tokens (e.g. on-behalf-of) and prepends a block to the user message:

    <sharepoint_auth>{"graph_token": "...", "sharepoint_token": "..."}</sharepoint_auth>

`graph_token`: audience https://graph.microsoft.com (Sites.Read.All, Files.Read.All).
`sharepoint_token` (optional): audience https://<tenant>.sharepoint.com (AllSites.Read); needed for the permission level.
The middleware strips the block (tokens never reach the model) and keeps them in a request-scoped context variable.
"""

from __future__ import annotations

import contextvars
import html
import io
import json
import re
from typing import Annotated, Any
from urllib.parse import quote, urlparse

import httpx
from agent_framework import AgentContext, AgentMiddleware, tool

GRAPH = "https://graph.microsoft.com/v1.0"
TOP = 10
MAX_DOWNLOAD = 10 * 1024 * 1024
MAX_TEXT = 6000
SHEET_ROWS = 50
PDF_PAGES = 30
# Legacy formats Graph can convert to PDF server-side (?format=pdf).
CONVERT_TO_PDF = {"doc", "ppt", "xls", "rtf", "odt", "odp", "ods", "pps"}

_AUTH_BLOCK = re.compile(r"<sharepoint_auth>(.*?)</sharepoint_auth>\s*", re.DOTALL)
_TOKEN = re.compile(r"^[A-Za-z0-9._\-~+/=]{20,8192}$")
_auth: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar("sharepoint_auth", default={})

# SharePoint base permission bits (low 32 bits of the mask).
_VIEW, _ADD, _EDIT, _DELETE = 0x1, 0x2, 0x4, 0x8
_MANAGE_PERMISSIONS, _MANAGE_WEB = 0x2000000, 0x40000000


def parse_auth(text: str) -> tuple[str, dict[str, str]]:
    """Return (text without auth blocks, validated tokens)."""
    tokens: dict[str, str] = {}
    for raw in _AUTH_BLOCK.findall(text):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            for key in ("graph_token", "sharepoint_token"):
                value = data.get(key)
                if isinstance(value, str) and _TOKEN.match(value):
                    tokens[key] = value
    return _AUTH_BLOCK.sub("", text).strip(), tokens


class SharePointAuthMiddleware(AgentMiddleware):
    async def process(self, context: AgentContext, call_next) -> None:
        tokens: dict[str, str] = {}
        for message in reversed(context.messages):
            if getattr(message, "role", None) != "user":
                continue
            for content in getattr(message, "contents", []) or []:
                text = getattr(content, "text", None)
                if text and "<sharepoint_auth>" in text:
                    content.text, found = parse_auth(text)
                    tokens.update(found)
            break
        _auth.set(tokens)
        await call_next()


def parse_site_url(url: str) -> tuple[str, str]:
    """Return (host, server-relative site path) for a SharePoint site URL; raises ValueError if invalid."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host.endswith(".sharepoint.com"):
        raise ValueError("Not a SharePoint Online URL (expected https://<tenant>.sharepoint.com/sites/<name>).")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0].lower() in ("sites", "teams"):
        return host, "/" + "/".join(parts[:2])
    return host, ""


def permission_level(mask_low: int) -> str:
    if mask_low & _MANAGE_PERMISSIONS and mask_low & _MANAGE_WEB:
        return "Full Control"
    if mask_low & _MANAGE_PERMISSIONS:
        return "Design/Manage"
    if mask_low & _EDIT and mask_low & _DELETE and mask_low & _ADD:
        return "Edit"
    if mask_low & _ADD and mask_low & _EDIT:
        return "Contribute"
    if mask_low & _VIEW:
        return "Read"
    return "Limited / none"


def _headers(key: str) -> dict[str, str]:
    token = _auth.get().get(key)
    if not token:
        raise PermissionError(f"Missing {key}. The chat app must pass the user's delegated token.")
    return {"Authorization": f"Bearer {token}"}


async def _get_site(client: httpx.AsyncClient, host: str, path: str) -> dict[str, Any]:
    url = f"{GRAPH}/sites/{host}:{quote(path)}" if path else f"{GRAPH}/sites/{host}"
    resp = await client.get(url, headers=_headers("graph_token"))
    if resp.status_code in (401, 403, 404):
        return {"error": resp.status_code}
    resp.raise_for_status()
    return resp.json()


async def _permission(client: httpx.AsyncClient, site_url: str) -> str | None:
    if "sharepoint_token" not in _auth.get():
        return None
    resp = await client.get(
        site_url.rstrip("/") + "/_api/web/effectiveBasePermissions",
        headers={**_headers("sharepoint_token"), "Accept": "application/json;odata=nometadata"},
    )
    if resp.status_code != 200:
        return None
    return permission_level(int(resp.json().get("Low", 0)))


@tool
async def check_site_access(
    site_url: Annotated[str, "SharePoint site URL, e.g. https://contoso.sharepoint.com/sites/Finance."],
) -> str:
    """Check whether the signed-in user can access the SharePoint site and which permission level they have."""
    try:
        host, path = parse_site_url(site_url)
        async with httpx.AsyncClient(timeout=30) as client:
            site = await _get_site(client, host, path)
            if "error" in site:
                return json.dumps(
                    {"has_access": False, "reason": "Site not found or the user has no access (HTTP %s)." % site["error"]}
                )
            level = await _permission(client, f"https://{host}{path}")
    except ValueError as exc:
        return json.dumps({"has_access": False, "reason": str(exc)})
    except PermissionError as exc:
        return json.dumps({"has_access": False, "reason": str(exc)})
    except Exception as exc:
        return json.dumps({"has_access": False, "reason": f"Check failed ({type(exc).__name__})."})
    return json.dumps(
        {
            "has_access": True,
            "site": site.get("displayName"),
            "site_url": site.get("webUrl"),
            "permission_level": level or "Unknown (SharePoint token not provided); at least Read",
        }
    )


def _sheet_text(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"[Sheet {ws.title}] ({ws.max_row} rows x {ws.max_column} cols)")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= SHEET_ROWS:
                out.append("...")
                break
            out.append(" | ".join("" if v is None else str(v) for v in row))
    wb.close()
    return "\n".join(out)


def _strip_html(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def _page_text(data: bytes) -> str:
    """Text of a SharePoint page (.aspx): the modern canvas web part HTML, else the stripped markup."""
    raw = data.decode("utf-8", errors="replace")
    match = re.search(r'data-sp-canvascontent1="([^"]*)"|CanvasContent1"?\s*[:=]\s*"?([^"]*)', raw)
    if match:
        try:
            blocks = json.loads(html.unescape(match.group(1) or match.group(2)))
            parts = [_strip_html(b["innerHTML"]) for b in blocks if isinstance(b, dict) and b.get("innerHTML")]
            if parts:
                return "\n".join(parts)
        except (ValueError, TypeError):
            pass
    return _strip_html(raw)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[:PDF_PAGES]
    return "\n".join((p.extract_text() or "") for p in pages)


def extract_text(name: str, data: bytes) -> str:
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext == "pdf":
        return _pdf_text(data)
    if ext in ("aspx", "html", "htm"):
        return _page_text(data)
    if ext in ("xlsx", "xlsm"):
        return _sheet_text(data)
    if ext == "docx":
        from docx import Document

        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs if p.text)
    if ext == "pptx":
        from pptx import Presentation

        return "\n".join(
            s.text_frame.text
            for slide in Presentation(io.BytesIO(data)).slides
            for s in slide.shapes
            if s.has_text_frame and s.text_frame.text
        )
    if ext in ("txt", "md", "csv", "json", "xml", "log"):
        return data.decode("utf-8", errors="replace")
    return ""


async def _fetch_content(client: httpx.AsyncClient, hit: dict[str, Any]) -> str:
    resource = hit.get("resource", {})
    drive, item = resource.get("parentReference", {}).get("driveId"), resource.get("id")
    if not (drive and item) or resource.get("size", 0) > MAX_DOWNLOAD:
        return ""
    try:
        name = resource.get("name", "")
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        convert = ext in CONVERT_TO_PDF
        resp = await client.get(
            f"{GRAPH}/drives/{drive}/items/{item}/content" + ("?format=pdf" if convert else ""),
            headers=_headers("graph_token"),
            follow_redirects=True,
        )
        resp.raise_for_status()
        return extract_text("converted.pdf" if convert else name, resp.content)[:MAX_TEXT]
    except Exception:
        return ""


@tool
async def search_sharepoint(
    query: Annotated[str, "Search keywords reformatted for SharePoint search (see instructions)."],
    site_url: Annotated[str, "SharePoint site URL the user gave; results are limited to this site."],
) -> str:
    """Search the site's files with SharePoint search as the signed-in user and return the top 10 results with content."""
    try:
        host, path = parse_site_url(site_url)
        scope = f"https://{host}{path}"
        body = {
            "requests": [
                {
                    "entityTypes": ["driveItem"],
                    "query": {"queryString": f'{query} path:"{scope}"'},
                    "from": 0,
                    "size": TOP,
                }
            ]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{GRAPH}/search/query", json=body, headers=_headers("graph_token"))
            resp.raise_for_status()
            containers = [c for v in resp.json().get("value", []) for c in v.get("hitsContainers", [])]
            hits = [h for c in containers for h in c.get("hits", [])][:TOP]
            results = []
            for rank, hit in enumerate(hits, 1):
                resource = hit.get("resource", {})
                results.append(
                    {
                        "rank": rank,
                        "name": resource.get("name"),
                        "url": resource.get("webUrl"),
                        "modified": resource.get("lastModifiedDateTime"),
                        "summary": re.sub(r"</?c0>|<ddd/>", "", hit.get("summary", "") or ""),
                        "content": await _fetch_content(client, hit),
                    }
                )
    except ValueError as exc:
        return f"Search failed: {exc}"
    except PermissionError as exc:
        return f"Search failed: {exc}"
    except Exception as exc:
        return f"Search failed ({type(exc).__name__}). Tell the user the search could not be completed."
    if not results:
        return "No results. Try broader or alternative keywords."
    return json.dumps(results, ensure_ascii=False)


SHAREPOINT_TOOLS = [check_site_access, search_sharepoint]
