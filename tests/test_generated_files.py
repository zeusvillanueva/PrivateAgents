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


def test_upload_sas_times_are_whole_second_utc(monkeypatch):
    from datetime import timezone
    from unittest.mock import AsyncMock, MagicMock, patch

    from shared import generated_files

    monkeypatch.setenv("STORAGE_ACCOUNT_URL", "https://acct.blob.core.windows.net")
    service = MagicMock(account_name="acct")
    service.get_user_delegation_key = AsyncMock(return_value="key")
    service.get_blob_client.return_value.upload_blob = AsyncMock()
    service.__aenter__ = AsyncMock(return_value=service)
    service.__aexit__ = AsyncMock(return_value=None)
    cred = MagicMock()
    cred.__aenter__ = AsyncMock(return_value=cred)
    cred.__aexit__ = AsyncMock(return_value=None)

    with patch("azure.storage.blob.generate_blob_sas", return_value="sig=1") as sas, \
            patch("azure.storage.blob.aio.BlobServiceClient", return_value=service), \
            patch("azure.identity.aio.DefaultAzureCredential", return_value=cred):
        url = asyncio.run(generated_files._upload(b"x", "a.pdf", "application/pdf"))

    assert url.endswith("?sig=1")
    key_start, key_expiry = service.get_user_delegation_key.call_args.args
    for value in (key_start, key_expiry, sas.call_args.kwargs["start"], sas.call_args.kwargs["expiry"]):
        assert value.microsecond == 0 and value.tzinfo == timezone.utc
