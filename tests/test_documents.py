import asyncio
import io
import zipfile

from shared import documents

SECTIONS = [{"heading": "H", "text": "t & <b>", "bullets": ["a", "b"], "table": [["x", "y"], [1, 2]]}]


def test_word_pptx_pdf_excel_build():
    for data in (documents.build_word("T", SECTIONS), documents.build_powerpoint("T", SECTIONS)):
        assert zipfile.is_zipfile(io.BytesIO(data))
    assert documents.build_pdf("T", SECTIONS).startswith(b"%PDF")
    xlsx = documents.build_excel([{"name": "a/b", "rows": [["h"], [1]]}])
    assert zipfile.is_zipfile(io.BytesIO(xlsx))


def test_tool_returns_link(monkeypatch):
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    out = asyncio.run(documents._finish(documents.build_pdf, "../my report", ".pdf", "T", SECTIONS))
    assert out.startswith("[Download my report.pdf](data:application/pdf;base64,")


def test_tool_error_is_reported():
    out = asyncio.run(documents._finish(documents.build_word, "a", ".docx", "T", [{"table": 5, "bullets": 3}]))
    assert out.startswith("Could not create")


def test_tools_invoke_with_validated_arguments(monkeypatch):
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    out = asyncio.run(documents.create_word.invoke(arguments={"title": "T", "sections": SECTIONS}))
    assert "Download report.docx" in out[0].text
