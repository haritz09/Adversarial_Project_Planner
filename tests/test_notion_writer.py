# tests/test_notion_writer.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.FAKE_STATE import FAKE_STATE
from tools.notion import notion_writer


def test_notion_writer_creates_pages():
    """Live test — creates real pages in Notion and verifies URLs are returned."""
    result = notion_writer(FAKE_STATE)

    assert "notion_urls" in result
    assert "notion_page_ids" in result
    assert result["current_node"] == "notion_writer"

    urls = result["notion_urls"]
    ids = result["notion_page_ids"]

    assert "root" in urls, "Root page URL missing"
    assert "root" in ids, "Root page ID missing"

    print("\nPages created in Notion:")
    for key, url in urls.items():
        print(f"  {key}: {url}")


def test_notion_writer_all_pages_present():
    """Verifies all expected pages were created."""
    result = notion_writer(FAKE_STATE)
    urls = result["notion_urls"]

    expected = ["root", "architecture", "scope", "plan_root", "plan"]
    for key in expected:
        assert key in urls, f"Missing page: {key}"

    print("✅ All expected pages created")