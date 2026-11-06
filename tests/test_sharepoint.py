import asyncio
import importlib.util
import pathlib

import pytest

import shared.sharepoint as sp


def test_parse_site_url():
    assert sp.parse_site_url("https://contoso.sharepoint.com/sites/Fin/Shared%20Documents/a.xlsx") == (
        "contoso.sharepoint.com",
        "/sites/Fin",
    )
    assert sp.parse_site_url("https://contoso.sharepoint.com/") == ("contoso.sharepoint.com", "")
    with pytest.raises(ValueError):
        sp.parse_site_url("https://evil.example.com/sites/x")
    with pytest.raises(ValueError):
        sp.parse_site_url("http://contoso.sharepoint.com/sites/x")


def test_permission_level():
    assert sp.permission_level(0xFFFFFFFF) == "Full Control"
    assert sp.permission_level(0x1 | 0x2 | 0x4 | 0x8) == "Edit"
    assert sp.permission_level(0x1 | 0x2 | 0x4) == "Contribute"
    assert sp.permission_level(0x1) == "Read"
    assert sp.permission_level(0) == "Limited / none"


def test_parse_auth_strips_and_validates():
    token = "a" * 40
    text, tokens = sp.parse_auth(f'<sharepoint_auth>{{"graph_token": "{token}", "sharepoint_token": "bad token"}}</sharepoint_auth>\nhi')
    assert text == "hi"
    assert tokens == {"graph_token": token}


def test_extract_excel_preview():
    import io

    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["a", "b"])
    wb.active.append([1, 2])
    buf = io.BytesIO()
    wb.save(buf)
    out = sp.extract_text("data.xlsx", buf.getvalue())
    assert "a | b" in out and "1 | 2" in out


def test_extract_page_text():
    page = b'<div data-sp-canvascontent1="[{&quot;innerHTML&quot;:&quot;&lt;p&gt;Leave policy &amp;amp; rules&lt;/p&gt;&quot;}]"></div>'
    assert "Leave policy & rules" in sp.extract_text("Home.aspx", page)
    assert "Hello" in sp.extract_text("a.aspx", b"<html><script>x()</script><p>Hello</p></html>")


def test_extract_pdf_text():
    pytest.importorskip("reportlab")
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Quarterly budget")
    c.save()
    assert "Quarterly budget" in sp.extract_text("b.pdf", buf.getvalue())


def test_check_site_access_requires_token():
    out = asyncio.run(sp.check_site_access.func(site_url="https://contoso.sharepoint.com/sites/x"))
    assert '"has_access": false' in out and "graph_token" in out


def test_agent(monkeypatch):
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "test")
    path = pathlib.Path(__file__).resolve().parents[1] / "agents" / "sharepoint" / "main.py"
    spec = importlib.util.spec_from_file_location("sharepoint_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.agent.name == "sharepoint-agent"
    assert "search_sharepoint" in module.INSTRUCTIONS
