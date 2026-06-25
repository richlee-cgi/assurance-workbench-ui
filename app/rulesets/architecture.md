---
id: architecture.decision_terms_missing
ruleset: architecture
severity: medium
applies_to_presets:
  - architecture
applies_to_sources:
  - confluence
  - jira
description: Architecture evidence does not show decision or trade-off terms.
follow_up: Ask where architecture decisions, alternatives and trade-offs are recorded.
---

# Architecture Decision Terms Missing

## Required Any Terms

- adr
- decision
- trade-off
- alternative
- constraint
- failure mode
- boundary

## Positive Terms

- integration
- dependency
- architecture

## Match Strategy

Raise a medium signal when architecture evidence is present but none of the required decision terms appear.
