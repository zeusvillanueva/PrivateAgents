import asyncio
import importlib.util
import pathlib

import shared.images as images


def test_base_url_uses_account_host():
    url = images.image_base_url("https://aif-img.services.ai.azure.com/api/projects/agents")
    assert url == "https://aif-img.services.ai.azure.com/openai/v1/"


def test_generate_image_stores_png(monkeypatch):
    seen = {}

    async def fake_generate(prompt, size, quality):
        seen.update(prompt=prompt, size=size, quality=quality)
        return b"png"

    async def fake_store(data, name):
        return f"![{name}](https://blob/{name})"

    monkeypatch.setattr(images, "generate_png", fake_generate)
    monkeypatch.setattr(images, "store_file", fake_store)
    out = asyncio.run(images.generate_image.func(prompt="a cat", size="bad", quality="bad"))
    assert out == "![image.png](https://blob/image.png)"
    assert seen == {"prompt": "a cat", "size": "1024x1024", "quality": "auto"}


def test_generate_image_failure_is_reported(monkeypatch):
    async def boom(*args):
        raise RuntimeError("x")

    monkeypatch.setattr(images, "generate_png", boom)
    assert "failed" in asyncio.run(images.generate_image.func(prompt="a cat"))


def test_agent(monkeypatch):
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "test")
    path = pathlib.Path(__file__).resolve().parents[1] / "agents" / "image-creator" / "main.py"
    spec = importlib.util.spec_from_file_location("image_creator_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.agent.name == "image-creator-agent"
    assert "generate_image" in module.INSTRUCTIONS
