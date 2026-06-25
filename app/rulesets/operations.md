---
id: operations.readiness_terms_missing
ruleset: operations
severity: medium
applies_to_presets:
  - architecture
  - operations
applies_to_sources:
  - confluence
  - jira
  - azure
description: Operational readiness terms were not found in retrieved evidence.
follow_up: Ask where monitoring, alerting, rollback and runbook evidence is recorded.
---

# Operational Readiness Terms Missing

## Required Any Terms

- monitoring
- alert
- alerting
- dashboard
- runbook
- rollback
- on-call
- support model
- incident
- sla
- slo

## Negative Terms

- no monitoring
- not monitored
- manual workaround
- temporary
- to be confirmed
- tbc
- todo

## Match Strategy

Raise a medium signal when none of the required operational readiness terms appear. Raise a high signal when negative operational terms appear.
