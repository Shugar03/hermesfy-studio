"""Tests for image generation history."""

import json
import pytest
from hermesfy.history import record_generation, query_history, get_history_stats, clear_history, _HISTORY_FILE
from hermesfy.tools.history import history_tool


@pytest.fixture(autouse=True)
def clean_history():
    """Clean history before and after tests."""
    clear_history()
    yield
    clear_history()


class TestRecordGeneration:
    def test_record_creates_entry(self):
        entry = record_generation(
            image_url="https://fal.ai/img.png",
            prompt="a red jar",
            model="flux-dev",
            pattern="simple",
        )
        assert entry["image_url"] == "https://fal.ai/img.png"
        assert entry["prompt"] == "a red jar"
        assert "timestamp" in entry

    def test_record_persists_to_file(self):
        record_generation(image_url="https://fal.ai/img.png", prompt="test")
        assert _HISTORY_FILE.exists()
        with open(_HISTORY_FILE) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1

    def test_record_appends_multiple(self):
        record_generation(image_url="https://fal.ai/1.png", prompt="one")
        record_generation(image_url="https://fal.ai/2.png", prompt="two")
        with open(_HISTORY_FILE) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2


class TestQueryHistory:
    def test_query_returns_newest_first(self):
        record_generation(image_url="https://fal.ai/1.png", prompt="first")
        record_generation(image_url="https://fal.ai/2.png", prompt="second")
        entries = query_history()
        assert len(entries) == 2
        assert entries[0]["prompt"] == "second"
        assert entries[1]["prompt"] == "first"

    def test_query_empty_history(self):
        assert query_history() == []

    def test_query_filter_by_model(self):
        record_generation(image_url="a", model="flux-dev")
        record_generation(image_url="b", model="flux-pro")
        dev = query_history(model="flux-dev")
        assert len(dev) == 1
        assert dev[0]["model"] == "flux-dev"

    def test_query_filter_by_pattern(self):
        record_generation(image_url="a", pattern="simple")
        record_generation(image_url="b", pattern="upscale")
        simple = query_history(pattern="simple")
        assert len(simple) == 1

    def test_query_filter_by_min_score(self):
        record_generation(image_url="a", qa_score=5)
        record_generation(image_url="b", qa_score=9)
        high = query_history(min_score=7)
        assert len(high) == 1
        assert high[0]["qa_score"] == 9

    def test_query_pagination(self):
        for i in range(5):
            record_generation(image_url=f"https://fal.ai/{i}.png", prompt=f"img{i}")
        page1 = query_history(limit=2, offset=0)
        page2 = query_history(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["prompt"] == "img4"  # newest first

    def test_query_filter_by_tag(self):
        record_generation(image_url="a", tags=["product", "studio"])
        record_generation(image_url="b", tags=["lifestyle"])
        tagged = query_history(tag="product")
        assert len(tagged) == 1


class TestHistoryStats:
    def test_stats_empty(self):
        stats = get_history_stats()
        assert stats["total"] == 0

    def test_stats_with_entries(self):
        record_generation(image_url="a", model="flux-dev", pattern="simple", qa_score=8)
        record_generation(image_url="b", model="flux-dev", pattern="upscale", qa_score=6)
        stats = get_history_stats()
        assert stats["total"] == 2
        assert stats["by_model"]["flux-dev"] == 2
        assert stats["avg_score"] == 7.0


class TestClearHistory:
    def test_clear_removes_all(self):
        record_generation(image_url="a", prompt="test")
        removed = clear_history()
        assert removed == 1
        assert query_history() == []


class TestHistoryTool:
    def test_list_action(self):
        record_generation(image_url="https://fal.ai/test.png", prompt="a jar")
        result = json.loads(history_tool(action="list"))
        assert result["count"] == 1
        assert result["entries"][0]["prompt"] == "a jar"

    def test_stats_action(self):
        record_generation(image_url="a", model="flux-dev", qa_score=8)
        result = json.loads(history_tool(action="stats"))
        assert result["total"] == 1
        assert result["by_model"]["flux-dev"] == 1

    def test_clear_action(self):
        record_generation(image_url="a", prompt="test")
        result = json.loads(history_tool(action="clear"))
        assert result["removed"] == 1

    def test_unknown_action(self):
        result = json.loads(history_tool(action="export"))
        assert "error" in result
