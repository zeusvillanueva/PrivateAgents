import importlib.util
import pathlib


def _load(monkeypatch):
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "test")
    path = pathlib.Path(__file__).resolve().parents[1] / "agents" / "markdown" / "main.py"
    spec = importlib.util.spec_from_file_location("markdown_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_agent(monkeypatch):
    module = _load(monkeypatch)
    assert module.agent.name == "markdown-agent"
    for keyword in ("Markdown", "README", "diagram-creator"):
        assert keyword in module.INSTRUCTIONS, keyword
