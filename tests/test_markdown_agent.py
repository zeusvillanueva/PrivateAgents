import re
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


def check_editor_safe(text):
    """Return problems that would make the WYSIWYG editor fall back to plain text."""
    problems = []
    if text.lstrip().startswith("```"):
        problems.append("leading code fence")
    if text.startswith("---\n"):
        problems.append("front matter")
    if re.search(r"</?[A-Za-z][^>]*>|<!--", text):
        problems.append("html")
    if re.search(r"\[\^[^\]]+\]", text):
        problems.append("footnote")
    return problems


def test_instructions_editor_rules(monkeypatch):
    text = _load(monkeypatch).INSTRUCTIONS
    for phrase in (
        "Never wrap it in a ```markdown fence",
        "explicitly asks for the raw source",
        "Never use raw HTML",
        "front matter",
        "footnotes",
        "exactly one \"# Title\"",
        "## Assumptions",
        "unless the user gives a URL",
        "never indented code blocks",
        "no pipes inside cells",
        "two-space nesting",
    ):
        assert phrase in text, phrase
    assert "Wrap a complete document" not in text


def test_checker():
    assert check_editor_safe("# Title\n\nHello\n") == []
    assert check_editor_safe("```markdown\n# T\n```") == ["leading code fence"]
    assert check_editor_safe("---\na: b\n---\n# T") == ["front matter"]
    assert check_editor_safe("# T\n\nline<br>x[^1]") == ["html", "footnote"]
