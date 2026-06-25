from pathlib import Path

from app.signals import load_builtin_rulesets, parse_rule_markdown


def test_load_builtin_rulesets() -> None:
    result = load_builtin_rulesets()

    assert not result.warnings
    assert {rule.ruleset for rule in result.rules} == {
        "architecture",
        "delivery",
        "operations",
        "risk",
        "security",
        "testing",
    }
    assert {rule.id for rule in result.rules} >= {
        "operations.readiness_terms_missing",
        "risk.known_bad_terms_present",
    }


def test_parse_rule_markdown_extracts_metadata_and_terms() -> None:
    markdown = """---
id: operations.example
ruleset: operations
severity: medium
applies_to_presets:
  - architecture
applies_to_sources:
  - confluence
description: Example description.
follow_up: Example follow-up.
---

# Example

## Required Any Terms

- monitoring
- runbook

## Negative Terms

- no monitoring

## Match Strategy

Raise a signal when required terms are missing.
"""

    rule, warnings = parse_rule_markdown(markdown, source_path="example.md")

    assert warnings == ()
    assert rule is not None
    assert rule.id == "operations.example"
    assert rule.ruleset == "operations"
    assert rule.applies_to_presets == ("architecture",)
    assert rule.applies_to_sources == ("confluence",)
    assert rule.required_any_terms == ("monitoring", "runbook")
    assert rule.negative_terms == ("no monitoring",)
    assert "required terms are missing" in rule.match_strategy
    assert rule.source_path == "example.md"


def test_parse_rule_markdown_reports_missing_front_matter() -> None:
    rule, warnings = parse_rule_markdown("# Missing front matter", source_path="broken.md")

    assert rule is None
    assert warnings == ("broken.md: missing YAML front matter",)


def test_parse_rule_markdown_reports_unsupported_sections() -> None:
    markdown = """---
id: testing.example
ruleset: testing
severity: medium
description: Example description.
follow_up: Example follow-up.
---

# Example

## Unsupported Things

- surprise
"""

    rule, warnings = parse_rule_markdown(markdown, source_path="unsupported.md")

    assert rule is not None
    assert warnings == ("unsupported.md: unsupported section: Unsupported Things",)


def test_load_rulesets_from_custom_directory(tmp_path: Path) -> None:
    (tmp_path / "custom.md").write_text(
        """---
id: delivery.custom
ruleset: delivery
severity: info
description: Custom rule.
follow_up: Custom follow-up.
---

# Custom

## Positive Terms

- shipped
""",
        encoding="utf-8",
    )

    result = load_builtin_rulesets(tmp_path)

    assert result.warnings == ()
    assert len(result.rules) == 1
    assert result.rules[0].positive_terms == ("shipped",)
