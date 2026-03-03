"""Tests for the markdown file utilities (data/markdown.py)."""

from pathlib import Path

import pytest

from policy_factory.data.markdown import parse_frontmatter, read_markdown, write_markdown

# ---------------------------------------------------------------------------
# parse_frontmatter (pure string parsing)
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    """Tests for the in-memory frontmatter parser."""

    def test_valid_frontmatter(self) -> None:
        text = "---\ntitle: Hello\nstatus: active\n---\nBody content here."
        fm, body = parse_frontmatter(text)
        assert fm == {"title": "Hello", "status": "active"}
        assert body == "Body content here."

    def test_no_frontmatter(self) -> None:
        text = "Just a plain markdown file.\nNo frontmatter."
        fm, body = parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_malformed_yaml(self) -> None:
        text = "---\n: invalid: yaml: [[\n---\nBody here."
        fm, body = parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_no_closing_delimiter(self) -> None:
        text = "---\ntitle: Oops\nNo closing delimiter."
        fm, body = parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_yaml_is_not_a_dict(self) -> None:
        """YAML that parses to a list or scalar should be treated as no frontmatter."""
        text = "---\n- item1\n- item2\n---\nBody."
        fm, body = parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_empty_frontmatter(self) -> None:
        """Empty YAML block parses as None, which we treat as no frontmatter."""
        text = "---\n\n---\nBody."
        fm, body = parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_body_with_leading_newline_stripped(self) -> None:
        text = "---\ntitle: Test\n---\n\nParagraph."
        fm, body = parse_frontmatter(text)
        assert fm == {"title": "Test"}
        assert body == "\nParagraph."

    def test_body_preserves_content(self) -> None:
        """Body should preserve all content after the closing delimiter."""
        text = "---\ntitle: Test\n---\nLine 1\nLine 2\n\nLine 4\n"
        fm, body = parse_frontmatter(text)
        assert fm == {"title": "Test"}
        assert body == "Line 1\nLine 2\n\nLine 4\n"

    def test_complex_frontmatter(self) -> None:
        text = (
            "---\n"
            "title: Complex Item\n"
            "status: active\n"
            "references:\n"
            "  - values/national-security.md\n"
            "  - values/eu-membership.md\n"
            "tags:\n"
            "  - defence\n"
            "  - nato\n"
            "---\n"
            "Body text."
        )
        fm, body = parse_frontmatter(text)
        assert fm["title"] == "Complex Item"
        assert fm["references"] == [
            "values/national-security.md",
            "values/eu-membership.md",
        ]
        assert body == "Body text."


# ---------------------------------------------------------------------------
# read_markdown (file I/O)
# ---------------------------------------------------------------------------


class TestReadMarkdown:
    """Tests for reading markdown files from disk."""

    def test_read_with_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Hello\n---\nBody.", encoding="utf-8")
        fm, body = read_markdown(f)
        assert fm == {"title": "Hello"}
        assert body == "Body."

    def test_read_without_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("Just plain text.", encoding="utf-8")
        fm, body = read_markdown(f)
        assert fm == {}
        assert body == "Just plain text."

    def test_read_malformed_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        content = "---\n: bad: yaml: [[\n---\nBody."
        f.write_text(content, encoding="utf-8")
        fm, body = read_markdown(f)
        assert fm == {}
        assert body == content

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_markdown(tmp_path / "missing.md")


# ---------------------------------------------------------------------------
# write_markdown (file I/O)
# ---------------------------------------------------------------------------


class TestWriteMarkdown:
    """Tests for writing markdown files to disk."""

    def test_write_with_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        write_markdown(f, {"title": "Hello", "status": "active"}, "Body content.")
        content = f.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "title: Hello" in content
        assert content.endswith("---\nBody content.")

    def test_write_empty_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        write_markdown(f, {}, "Just body.")
        content = f.read_text(encoding="utf-8")
        assert content == "Just body."
        assert "---" not in content

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        f = tmp_path / "sub" / "dir" / "test.md"
        write_markdown(f, {"title": "Nested"}, "Deep body.")
        assert f.exists()
        fm, body = read_markdown(f)
        assert fm["title"] == "Nested"
        assert body == "Deep body."


# ---------------------------------------------------------------------------
# Round-trip integrity
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Writing then reading must produce identical data."""

    def test_simple_roundtrip(self, tmp_path: Path) -> None:
        f = tmp_path / "rt.md"
        original_fm = {"title": "Round Trip", "status": "active"}
        original_body = "This is the body.\n\nWith paragraphs.\n"

        write_markdown(f, original_fm, original_body)
        fm, body = read_markdown(f)

        assert fm == original_fm
        assert body == original_body

    def test_roundtrip_with_list_values(self, tmp_path: Path) -> None:
        f = tmp_path / "rt.md"
        original_fm = {
            "title": "With Lists",
            "references": ["values/a.md", "values/b.md"],
        }
        original_body = "Body.\n"

        write_markdown(f, original_fm, original_body)
        fm, body = read_markdown(f)

        assert fm == original_fm
        assert body == original_body

    def test_roundtrip_empty_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "rt.md"
        original_body = "No frontmatter here."

        write_markdown(f, {}, original_body)
        fm, body = read_markdown(f)

        assert fm == {}
        assert body == original_body

    def test_roundtrip_unicode(self, tmp_path: Path) -> None:
        f = tmp_path / "rt.md"
        original_fm = {"title": "Suomalainen arvo"}
        original_body = "Tasa-arvo ja oikeudenmukaisuus ovat perusarvoja.\n"

        write_markdown(f, original_fm, original_body)
        fm, body = read_markdown(f)

        assert fm == original_fm
        assert body == original_body
