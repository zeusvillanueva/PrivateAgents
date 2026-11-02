import importlib.util
import pathlib

KEYWORDS = (
    "<phase>build</phase>", "<deployments>", "<tools>", "<agents>", '"status":"ask"', '"status":"ready"',
    "needsKnowledgeFiles", "require_approval", "file_search", "mcp", "web search", "https",
)


def _load(monkeypatch):
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "test")
    path = pathlib.Path(__file__).resolve().parents[1] / "agents" / "agent-builder" / "main.py"
    spec = importlib.util.spec_from_file_location("agent_builder_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_instructions_guard(monkeypatch):
    module = _load(monkeypatch)
    for keyword in KEYWORDS:
        assert keyword in module.INSTRUCTIONS, keyword
    assert module.agent.name == "agent-builder-agent"
