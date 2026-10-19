import asyncio
from types import SimpleNamespace

from shared.generated_files import MAX_BYTES, _citations, _markdown


class _Resp:
    def __init__(self, data):
        self._data = data

    async def aread(self):
        return self._data


def _client(data):
    async def retrieve(file_id, container_id):
        return _Resp(data)

    return SimpleNamespace(containers=SimpleNamespace(files=SimpleNamespace(content=SimpleNamespace(retrieve=retrieve))))


def test_citations_from_annotation():
    content = SimpleNamespace(
        annotations=[{"file_id": "cfile_1", "url": "a.png", "additional_properties": {"container_id": "cntr_1"}}]
    )
    assert _citations(content) == [("cntr_1", "cfile_1", "a.png")]


def test_markdown_image_and_file():
    img = asyncio.run(_markdown(_client(b"png"), "c", "f", "chart.png"))
    assert img.strip().startswith("![chart.png](data:image/png;base64,")
    doc = asyncio.run(_markdown(_client(b"x"), "c", "f", "../r.pdf"))
    assert "[Download r.pdf](data:application/pdf;base64," in doc


def test_markdown_too_large():
    assert "too large" in asyncio.run(_markdown(_client(b"x" * (MAX_BYTES + 1)), "c", "f", "big.png"))
