"""Tests for workflow templates and list_templates tool."""

import json
import pytest
from hermesfy.templates import list_templates, get_template, instantiate_template, template_to_json
from hermesfy.tools.list_templates import list_templates_tool
from hermesfy.tools.workflows import workflows


@pytest.fixture(autouse=True)
def clear_workflows():
    workflows.clear()
    yield
    workflows.clear()


class TestTemplates:
    def test_list_templates_returns_six(self):
        templates = list_templates()
        assert len(templates) == 6

    def test_all_templates_have_required_fields(self):
        for t in list_templates():
            assert "key" in t
            assert "name" in t
            assert "description" in t
            assert "category" in t
            assert "nodes" in t

    def test_get_template_returns_dict(self):
        tmpl = get_template("product_studio")
        assert tmpl is not None
        assert tmpl["name"] == "Product Studio"
        assert "nodes" in tmpl
        assert "edges" in tmpl

    def test_get_template_missing_returns_none(self):
        assert get_template("nonexistent") is None

    def test_instantiate_template_creates_workflow(self):
        wf = instantiate_template("product_studio", "red jar")
        assert wf is not None
        assert wf.name == "Product Studio"
        assert len(wf.nodes) == 3
        assert len(wf.edges) == 2
        # Check description replacement
        prompt_node = next(n for n in wf.nodes if n.id == "prompt")
        assert "red jar" in prompt_node.config["prompt"]

    def test_instantiate_with_empty_description(self):
        wf = instantiate_template("product_studio")
        assert wf is not None
        prompt_node = next(n for n in wf.nodes if n.id == "prompt")
        # With empty description, placeholder remains (user fills it)
        assert "white background" in prompt_node.config["prompt"]

    def test_template_to_json_format(self):
        data = template_to_json("product_studio", "blue cream")
        assert data is not None
        assert "name" in data
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 3
        # Verify JSON serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0

    def test_template_to_json_missing_returns_none(self):
        assert template_to_json("nonexistent") is None

    def test_all_templates_produce_valid_workflows(self):
        """Every template should produce a valid workflow."""
        for t in list_templates():
            wf = instantiate_template(t["key"], "test product")
            assert wf is not None, f"Template {t['key']} failed to instantiate"
            assert len(wf.nodes) > 0, f"Template {t['key']} has no nodes"
            assert len(wf.edges) > 0, f"Template {t['key']} has no edges"


class TestListTemplatesTool:
    def test_list_action(self):
        result = json.loads(list_templates_tool(action="list"))
        assert "templates" in result
        assert result["count"] == 6

    def test_inspect_action(self):
        result = json.loads(list_templates_tool(action="inspect", template_key="product_studio"))
        assert result["name"] == "Product Studio"
        assert "nodes" in result

    def test_inspect_missing_returns_error(self):
        result = json.loads(list_templates_tool(action="inspect", template_key="nope"))
        assert "error" in result

    def test_export_action(self):
        result = json.loads(list_templates_tool(action="export", template_key="product_studio", description="a jar"))
        assert "nodes" in result
        assert "edges" in result
        # Description should be injected
        prompt_node = next(n for n in result["nodes"] if n["id"] == "prompt")
        assert "a jar" in prompt_node["config"]["prompt"]

    def test_unknown_action_returns_error(self):
        result = json.loads(list_templates_tool(action="delete"))
        assert "error" in result
