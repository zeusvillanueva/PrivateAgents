import importlib.util
import pathlib


def test_diagram_creator_agent(monkeypatch):
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "test")
    path = pathlib.Path(__file__).resolve().parents[1] / "agents" / "diagram-creator" / "main.py"
    spec = importlib.util.spec_from_file_location("diagram_creator_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.agent.name == "diagram-creator-agent"
    for keyword in ("```mermaid", "flowchart", "sequenceDiagram", "erDiagram", "gantt"):
        assert keyword in module.INSTRUCTIONS, keyword
