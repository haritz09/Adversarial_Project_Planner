import sys

from sinks.notion import markdown_to_blocks


def types_of(blocks):
    return [b["type"] for b in blocks]

def text_of(block):
    key = block["type"]
    return block[key]["rich_text"][0]["text"]["content"]

def test_heading_1():
    blocks = markdown_to_blocks("# Hello")
    assert blocks[0]["type"] == "heading_1"
    assert text_of(blocks[0]) == "Hello"
    print("✅ heading_1")

def test_heading_2():
    blocks = markdown_to_blocks("## Hello")
    assert blocks[0]["type"] == "heading_2"
    assert text_of(blocks[0]) == "Hello"
    print("✅ heading_2")

def test_heading_3():
    blocks = markdown_to_blocks("### Hello")
    assert blocks[0]["type"] == "heading_3"
    assert text_of(blocks[0]) == "Hello"
    print("✅ heading_3")

def test_bullet_dash():
    blocks = markdown_to_blocks("- item one")
    assert blocks[0]["type"] == "bulleted_list_item"
    assert text_of(blocks[0]) == "item one"
    print("✅ bullet with dash")

def test_bullet_asterisk():
    blocks = markdown_to_blocks("* item one")
    assert blocks[0]["type"] == "bulleted_list_item"
    print("✅ bullet with asterisk")

def test_numbered_list():
    md = "1. First\n2. Second\n3. Third"
    blocks = markdown_to_blocks(md)
    assert all(b["type"] == "numbered_list_item" for b in blocks)
    assert len(blocks) == 3
    print("✅ numbered list")

def test_paragraph():
    blocks = markdown_to_blocks("Just a plain paragraph.")
    assert blocks[0]["type"] == "paragraph"
    assert text_of(blocks[0]) == "Just a plain paragraph."
    print("✅ paragraph")

def test_code_block_python():
    md = "```python\nprint('hello')\n```"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "python"
    assert "print" in blocks[0]["code"]["rich_text"][0]["text"]["content"]
    print("✅ python code block")

def test_code_block_mermaid():
    md = "```mermaid\ngraph TD\nA-->B\n```"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "mermaid"
    print("✅ mermaid code block")

def test_code_block_unknown_language():
    md = "```unknownlang\nsome code\n```"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["code"]["language"] == "plain text"
    print("✅ unknown language falls back to plain text")

def test_table_basic():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "table"
    assert blocks[0]["table"]["table_width"] == 2
    assert blocks[0]["table"]["has_column_header"]
    print("✅ basic table")

def test_table_three_columns():
    md = "| Risk | Prob | Impact |\n|---|---|---|\n| Auth delay | Medium | High |"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["table"]["table_width"] == 3
    print("✅ three column table")

def test_empty_lines_ignored():
    md = "## Title\n\n\n- item\n\n"
    blocks = markdown_to_blocks(md)
    assert len(blocks) == 2
    print("✅ empty lines ignored")

def test_mixed_content():
    md = "## Title\n- item 1\n- item 2\n\nParagraph text"
    blocks = markdown_to_blocks(md)
    assert types_of(blocks) == [
        "heading_2", "bulleted_list_item", "bulleted_list_item", "paragraph"
    ]
    print("✅ mixed clean content")

def test_introductory_text_before_heading():
    md = "Here is the architectural overview for your project.\n\n## Chosen Stack\n- React\n- Firebase"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "paragraph"
    assert blocks[1]["type"] == "heading_2"
    assert blocks[2]["type"] == "bulleted_list_item"
    print("✅ introductory text before heading")

def test_bold_inline_stripped_to_text():
    md = "The team will use **React** with **Firebase** for the following reasons:"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "paragraph"

    assert "React" in text_of(blocks[0])
    print("✅ bold inline does not crash parser")

def test_table_with_alignment_markers():
    md = "| Risk | Prob | Impact |\n|:---|:---:|:---:|\n| OAuth | Medium | High |"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "table"
    assert blocks[0]["table"]["table_width"] == 3
    print("✅ table with alignment markers in separator")

def test_table_with_extra_spaces():
    md = "|  Task  |  Phase  |  Effort  |\n|---|---|---|\n|  Setup  |  1  |  2-4h  |"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "table"
    cells = blocks[0]["table"]["children"][0]["table_row"]["cells"]
    assert cells[0][0]["text"]["content"] == "Task"
    print("✅ table cells with extra spaces are stripped")

def test_table_with_empty_cells():
    md = "| A | B | C |\n|---|---|---|\n| 1 | 2 |"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "table"
    assert blocks[0]["table"]["table_width"] == 3

    header_cells = blocks[0]["table"]["children"][0]["table_row"]["cells"]
    assert len(header_cells) == 3
    assert header_cells[0][0]["text"]["content"] == "A"

    data_cells = blocks[0]["table"]["children"][1]["table_row"]["cells"]
    assert len(data_cells) == 3
    assert data_cells[2][0]["text"]["content"] == ""
    print("✅ table with missing cells padded correctly")

def test_blockquote_treated_as_paragraph():
    md = "> Note: OAuth integration may require additional time."
    blocks = markdown_to_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"
    print("✅ blockquote treated as paragraph without crash")

def test_heading_with_trailing_spaces():
    md = "## Title with trailing spaces   "
    blocks = markdown_to_blocks(md)
    assert text_of(blocks[0]) == "Title with trailing spaces"
    print("✅ heading trailing spaces stripped")

def test_consecutive_code_blocks():
    md = "```python\ncode_a()\n```\n```mermaid\ngraph TD\nA-->B\n```"
    blocks = markdown_to_blocks(md)
    assert len(blocks) == 2
    assert blocks[0]["code"]["language"] == "python"
    assert blocks[1]["code"]["language"] == "mermaid"
    print("✅ consecutive code blocks")

def test_unclosed_code_block():
    md = "```python\nsome code without closing fence"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "code"
    assert "some code" in blocks[0]["code"]["rich_text"][0]["text"]["content"]
    print("✅ unclosed code block handled without crash")

def test_multiple_tables_in_document():
    md = (
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "Some text in between.\n\n"
        "| X | Y | Z |\n|---|---|---|\n| a | b | c |"
    )
    blocks = markdown_to_blocks(md)
    table_blocks = [b for b in blocks if b["type"] == "table"]
    assert len(table_blocks) == 2
    assert table_blocks[0]["table"]["table_width"] == 2
    assert table_blocks[1]["table"]["table_width"] == 3
    print("✅ multiple tables in same document")

def test_full_realistic_llm_output():
    md = """\
Here is the architectural overview based on the debate conclusions.

## Chosen Stack

The following technologies were selected for this project:

- **Frontend**: React 18 with TypeScript
- **Real-time**: Firebase Realtime Database
- **Auth**: Node.js + Express middleware

## System Components

1. React Client — handles UI and Firebase connection
2. Firebase Realtime Database — syncs messages
3. Node.js Auth Service — wraps existing OAuth

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|:---|:---:|:---:|:---|
| OAuth delay | Medium | High | Timebox to day 2 |
| Rules misconfiguration | Low | High | Use Firebase emulator |
| Scope creep | Low | Medium | Share MVP doc upfront |

## Architecture Diagram

```mermaid
graph TD
    A[React Client] --> B[Firebase DB]
    A --> C[Node Auth]
    C --> D[OAuth Provider]
```

> Note: The Node.js auth service should be kept stateless for easier scaling.
"""
    blocks = markdown_to_blocks(md)
    block_types = types_of(blocks)

    assert "paragraph" in block_types
    assert "heading_2" in block_types
    assert "bulleted_list_item" in block_types
    assert "numbered_list_item" in block_types
    assert "table" in block_types
    assert "code" in block_types
    assert len(blocks) > 10
    print(f"✅ full realistic LLM output parsed ({len(blocks)} blocks)")

ALL_TESTS = [
    test_heading_1, test_heading_2, test_heading_3,
    test_bullet_dash, test_bullet_asterisk, test_numbered_list,
    test_paragraph, test_code_block_python, test_code_block_mermaid,
    test_code_block_unknown_language, test_table_basic,
    test_table_three_columns, test_empty_lines_ignored, test_mixed_content,

    test_introductory_text_before_heading,
    test_bold_inline_stripped_to_text,
    test_table_with_alignment_markers,
    test_table_with_extra_spaces,
    test_table_with_empty_cells,
    test_blockquote_treated_as_paragraph,
    test_heading_with_trailing_spaces,
    test_consecutive_code_blocks,
    test_unclosed_code_block,
    test_multiple_tables_in_document,
    test_full_realistic_llm_output,
]

if __name__ == "__main__":
    print("═" * 60)
    print("MARKDOWN → NOTION BLOCKS TESTS")
    print("═" * 60)
    passed = failed = 0
    for t in ALL_TESTS:
        try:
            print(f"\n▶ {t.__name__}")
            t()
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
    print(f"\n{'═' * 60}")
    print(f"{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
