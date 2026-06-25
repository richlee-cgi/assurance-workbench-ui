from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RULESETS_DIR = Path(__file__).resolve().parent / "rulesets"

SUPPORTED_TERM_SECTIONS = {
    "required any terms": "required_any_terms",
    "required all terms": "required_all_terms",
    "positive terms": "positive_terms",
    "negative terms": "negative_terms",
}
SUPPORTED_TEXT_SECTIONS = {"match strategy"}
REQUIRED_METADATA = ("id", "ruleset", "severity", "description", "follow_up")


@dataclass(frozen=True)
class SignalRule:
    id: str
    ruleset: str
    severity: str
    description: str
    follow_up: str
    applies_to_presets: tuple[str, ...]
    applies_to_sources: tuple[str, ...]
    required_any_terms: tuple[str, ...]
    required_all_terms: tuple[str, ...]
    positive_terms: tuple[str, ...]
    negative_terms: tuple[str, ...]
    match_strategy: str
    source_path: str


@dataclass(frozen=True)
class RulesetLoadResult:
    rules: tuple[SignalRule, ...]
    warnings: tuple[str, ...]


def load_builtin_rulesets(rulesets_dir: Path = RULESETS_DIR) -> RulesetLoadResult:
    rules: list[SignalRule] = []
    warnings: list[str] = []
    for path in sorted(rulesets_dir.glob("*.md")):
        rule, file_warnings = parse_rule_markdown(path.read_text(encoding="utf-8"), source_path=str(path))
        warnings.extend(file_warnings)
        if rule is not None:
            rules.append(rule)
    return RulesetLoadResult(rules=tuple(rules), warnings=tuple(warnings))


def parse_rule_markdown(markdown: str, *, source_path: str = "") -> tuple[SignalRule | None, tuple[str, ...]]:
    warnings: list[str] = []
    metadata, body = _split_front_matter(markdown, warnings, source_path)
    if metadata is None:
        return None, tuple(warnings)

    missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
    if missing:
        warnings.append(f"{source_path or '<ruleset>'}: missing required metadata: {', '.join(missing)}")
        return None, tuple(warnings)

    sections = _parse_sections(body, warnings, source_path)
    terms = {field: tuple(sections.get(field, ())) for field in SUPPORTED_TERM_SECTIONS.values()}

    return (
        SignalRule(
            id=str(metadata["id"]),
            ruleset=str(metadata["ruleset"]),
            severity=str(metadata["severity"]),
            description=str(metadata["description"]),
            follow_up=str(metadata["follow_up"]),
            applies_to_presets=tuple(metadata.get("applies_to_presets", ())),
            applies_to_sources=tuple(metadata.get("applies_to_sources", ())),
            required_any_terms=terms["required_any_terms"],
            required_all_terms=terms["required_all_terms"],
            positive_terms=terms["positive_terms"],
            negative_terms=terms["negative_terms"],
            match_strategy="\n".join(sections.get("match strategy", ())).strip(),
            source_path=source_path,
        ),
        tuple(warnings),
    )


def _split_front_matter(markdown: str, warnings: list[str], source_path: str) -> tuple[dict[str, object] | None, str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        warnings.append(f"{source_path or '<ruleset>'}: missing YAML front matter")
        return None, markdown

    try:
        end_index = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        warnings.append(f"{source_path or '<ruleset>'}: unterminated YAML front matter")
        return None, markdown

    metadata = _parse_front_matter(lines[1:end_index], warnings, source_path)
    return metadata, "\n".join(lines[end_index + 1 :])


def _parse_front_matter(lines: list[str], warnings: list[str], source_path: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    current_list_key: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_list_key:
            value = stripped[2:].strip()
            existing = metadata.setdefault(current_list_key, [])
            if isinstance(existing, list):
                existing.append(value)
            continue
        if ":" not in line:
            warnings.append(f"{source_path or '<ruleset>'}: unsupported front matter line: {line}")
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            metadata[key] = value.strip('"')
            current_list_key = None
        else:
            metadata[key] = []
            current_list_key = key
    return metadata


def _parse_sections(body: str, warnings: list[str], source_path: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            if heading in SUPPORTED_TERM_SECTIONS:
                current_heading = SUPPORTED_TERM_SECTIONS[heading]
                sections.setdefault(current_heading, [])
            elif heading in SUPPORTED_TEXT_SECTIONS:
                current_heading = heading
                sections.setdefault(current_heading, [])
            else:
                warnings.append(f"{source_path or '<ruleset>'}: unsupported section: {stripped[3:].strip()}")
                current_heading = None
            continue
        if current_heading is None or not stripped:
            continue
        if current_heading in SUPPORTED_TERM_SECTIONS.values():
            if stripped.startswith("- "):
                sections[current_heading].append(stripped[2:].strip())
            elif not stripped.startswith("#"):
                warnings.append(f"{source_path or '<ruleset>'}: unsupported term line: {line}")
        elif current_heading in SUPPORTED_TEXT_SECTIONS:
            sections[current_heading].append(stripped)
    return sections
