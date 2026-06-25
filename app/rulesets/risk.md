---
id: risk.known_bad_terms_present
ruleset: risk
severity: high
applies_to_presets:
  - risk
  - delivery
  - operations
applies_to_sources:
  - confluence
  - jira
  - azure
  - dataverse
  - code
description: Retrieved evidence contains known risk or failure markers.
follow_up: Review whether each risk marker has a current owner, mitigation or decision.
---

# Known Risk Terms Present

## Negative Terms

- risk
- blocker
- incident
- defect
- vulnerability
- unsupported
- warning
- failed
- unresolved
- workaround
- temporary

## Positive Terms

- mitigation
- owner
- decision
- resolved

## Match Strategy

Raise a high signal when known risk terms appear without nearby mitigation, owner or decision language.
