"""Unit tests for seed router helper functions.

Tests _slugify() and _parse_values_output() — module-private parsing helpers
that have no existing test coverage. These functions are critical for the
values seed pipeline: _parse_values_output() extracts value documents from
the agent's response, and _slugify() converts titles to filename-safe slugs.

Importing private (_-prefixed) functions is intentional here — these are
internal parsing functions that need direct unit testing.
"""

from __future__ import annotations

from policy_factory.server.routers.seed import _parse_values_output, _slugify

# ---------------------------------------------------------------------------
# _slugify() tests
# ---------------------------------------------------------------------------


class TestSlugify:
    """Tests for the _slugify() function."""

    def test_simple_title(self) -> None:
        """Simple multi-word title produces a hyphenated lowercase slug."""
        assert _slugify("National Security") == "national-security"

    def test_tension_pair_with_vs(self) -> None:
        """Tension-pair title with 'vs.' produces a valid non-empty slug."""
        result = _slugify("Military Sovereignty vs. Alliance Dependence")
        assert result
        assert "vs" in result
        assert result == "military-sovereignty-vs-alliance-dependence"

    def test_tension_pair_with_vs_no_dot(self) -> None:
        """Tension-pair title with 'vs' (no dot) produces a valid slug."""
        result = _slugify("Welfare Generosity vs Work Incentives")
        assert result
        assert "vs" in result
        assert result == "welfare-generosity-vs-work-incentives"

    def test_title_with_ampersand(self) -> None:
        """Ampersand is stripped from the slug."""
        result = _slugify("Ethnic & Cultural Cohesion vs. Open Immigration")
        assert result
        assert "&" not in result
        # The & is removed, so "ethnic" and "cultural" are still present
        assert "ethnic" in result
        assert "cultural" in result
        assert "cohesion" in result

    def test_long_multi_word_title(self) -> None:
        """Long title produces a reasonable slug without truncation issues."""
        result = _slugify(
            "Individual Freedom and Personal Autonomy vs. Collective Security "
            "and Social Responsibility"
        )
        assert result
        assert len(result) > 10  # It should be a substantial slug
        assert result.startswith("individual-freedom")

    def test_lowercase_normalization(self) -> None:
        """Mixed case is normalized to lowercase."""
        result = _slugify("NATO Alliance vs. National Independence")
        assert result == result.lower()
        assert "nato" in result

    def test_empty_string(self) -> None:
        """Empty string produces an empty slug."""
        assert _slugify("") == ""

    def test_special_characters_stripped(self) -> None:
        """Special characters (parentheses, colons, etc.) are removed."""
        result = _slugify("Security (Internal) vs. Freedom: A Dilemma")
        assert "(" not in result
        assert ")" not in result
        assert ":" not in result
        assert result  # Non-empty

    def test_unicode_normalization(self) -> None:
        """Unicode characters are normalized to ASCII equivalents."""
        result = _slugify("Saamelaisten Oikeudet vs. Valtio")
        assert result
        # All characters should be ASCII
        assert result.encode("ascii")

    def test_collapses_multiple_hyphens(self) -> None:
        """Multiple consecutive special chars don't produce multiple hyphens."""
        result = _slugify("A & B -- C")
        assert "--" not in result

    def test_strips_leading_trailing_hyphens(self) -> None:
        """Leading and trailing hyphens are stripped."""
        result = _slugify("---test---")
        assert not result.startswith("-")
        assert not result.endswith("-")
        assert result == "test"

    def test_dots_stripped(self) -> None:
        """Dots (e.g., from 'vs.') are stripped."""
        result = _slugify("A vs. B")
        assert "." not in result
        assert result == "a-vs-b"


# ---------------------------------------------------------------------------
# _parse_values_output() tests
# ---------------------------------------------------------------------------


class TestParseValuesOutput:
    """Tests for the _parse_values_output() function."""

    def test_parses_multiple_tension_pairs(self) -> None:
        """Well-formed output with multiple tension-pairs is parsed correctly."""
        output = """
---
title: "Ethnic & Cultural Cohesion vs. Open Immigration"
tensions:
  - "Welfare Generosity vs. Work Incentives"
  - "National Identity vs. European Integration"
---

Finland sits at a crossroads between its ethnically homogeneous past and
the demographic pressures of an aging population.

---
title: "Military Sovereignty vs. Alliance Dependence"
tensions:
  - "Ethnic & Cultural Cohesion vs. Open Immigration"
---

Finland maintained a credible independent defense for decades. NATO membership
changes the calculus fundamentally.

---
title: "Welfare Generosity vs. Work Incentives"
tensions:
  - "Ethnic & Cultural Cohesion vs. Open Immigration"
  - "Military Sovereignty vs. Alliance Dependence"
---

The Nordic model promises generous safety nets. An aging society with a
shrinking workforce cannot sustain generosity without behavioral effects.
"""
        result = _parse_values_output(output)

        assert len(result) == 3

        # Check first value
        fm1, body1 = result[0]
        assert fm1["title"] == "Ethnic & Cultural Cohesion vs. Open Immigration"
        assert len(fm1["tensions"]) == 2
        assert "ethnically homogeneous" in body1

        # Check second value
        fm2, body2 = result[1]
        assert fm2["title"] == "Military Sovereignty vs. Alliance Dependence"
        assert "NATO membership" in body2

        # Check third value
        fm3, body3 = result[2]
        assert fm3["title"] == "Welfare Generosity vs. Work Incentives"
        assert "Nordic model" in body3

    def test_extracts_title_from_frontmatter(self) -> None:
        """The title field is correctly extracted with tension-pair format."""
        output = """
---
title: "Individual Freedom vs. Collective Security"
tensions:
  - "Other Tension"
---

Body content here.
"""
        result = _parse_values_output(output)
        assert len(result) == 1
        fm, _ = result[0]
        assert fm["title"] == "Individual Freedom vs. Collective Security"

    def test_extracts_tensions_list(self) -> None:
        """The tensions list in frontmatter is correctly parsed."""
        output = """
---
title: "Test Tension"
tensions:
  - "Related Tension A"
  - "Related Tension B"
  - "Related Tension C"
---

Body content here.
"""
        result = _parse_values_output(output)
        assert len(result) == 1
        fm, _ = result[0]
        assert fm["tensions"] == [
            "Related Tension A",
            "Related Tension B",
            "Related Tension C",
        ]

    def test_skips_block_missing_title(self) -> None:
        """Blocks without a title field are skipped without crashing."""
        output = """
---
tensions:
  - "Something"
---

This block has no title and should be skipped.

---
title: "Valid Tension"
tensions:
  - "Something"
---

This block has a title and should be parsed.
"""
        result = _parse_values_output(output)
        assert len(result) == 1
        assert result[0][0]["title"] == "Valid Tension"

    def test_skips_invalid_yaml(self) -> None:
        """Blocks with invalid YAML are skipped without crashing."""
        output = """
---
title: "Valid Before"
tensions:
  - "Other"
---

Valid block before the bad one.

---
: invalid: yaml: [broken
  - not: valid
---

This block has bad YAML.

---
title: "Valid After"
tensions:
  - "Other"
---

Valid block after the bad one.
"""
        result = _parse_values_output(output)
        # At least the valid blocks should parse
        titles = [fm["title"] for fm, _ in result]
        assert "Valid Before" in titles

    def test_empty_output_returns_empty_list(self) -> None:
        """Output with no valid blocks returns an empty list."""
        result = _parse_values_output("")
        assert result == []

    def test_no_frontmatter_returns_empty_list(self) -> None:
        """Output without any frontmatter delimiters returns empty list."""
        result = _parse_values_output("Just some text without any frontmatter.")
        assert result == []

    def test_single_value_parsed(self) -> None:
        """A single well-formed value is parsed correctly."""
        output = """
---
title: "Nuclear Energy vs. Renewable Transition"
tensions:
  - "Economic Growth vs. Environmental Protection"
---

Finland operates four nuclear reactors and recently commissioned Olkiluoto 3.
The tension between nuclear baseload and renewable targets is real.
"""
        result = _parse_values_output(output)
        assert len(result) == 1
        fm, body = result[0]
        assert fm["title"] == "Nuclear Energy vs. Renewable Transition"
        assert "Olkiluoto" in body

    def test_body_text_is_stripped(self) -> None:
        """Body text has leading/trailing whitespace stripped."""
        output = """
---
title: "Test Value"
tensions: []
---

  Body with leading spaces and trailing newlines.

"""
        result = _parse_values_output(output)
        assert len(result) == 1
        _, body = result[0]
        # Body should be stripped
        assert not body.startswith(" ")
        assert not body.endswith("\n")

    def test_frontmatter_without_tensions_still_parses(self) -> None:
        """Values without tensions field still parse (tensions is optional)."""
        output = """
---
title: "Minimal Value"
---

Body content with no tensions listed.
"""
        result = _parse_values_output(output)
        assert len(result) == 1
        fm, _ = result[0]
        assert fm["title"] == "Minimal Value"
        assert fm.get("tensions") is None

    def test_title_with_special_characters(self) -> None:
        """Titles with ampersands and dots parse correctly."""
        output = """
---
title: "Ethnic & Cultural Cohesion vs. Open Immigration"
tensions: []
---

Body.
"""
        result = _parse_values_output(output)
        assert len(result) == 1
        assert result[0][0]["title"] == "Ethnic & Cultural Cohesion vs. Open Immigration"
