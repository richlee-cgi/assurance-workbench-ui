---
id: delivery.risk_markers_present
ruleset: delivery
severity: medium
applies_to_presets:
  - delivery
  - risk
applies_to_sources:
  - jira
  - confluence
description: Delivery evidence contains risk, blocker, incident or workaround markers.
follow_up: Review whether the delivery risks have owners, mitigations and current status.
---

# Delivery Risk Markers Present

## Negative Terms

- blocked
- blocker
- incident
- defect
- bug
- workaround
- dependency
- delayed
- overdue
- unresolved

## Positive Terms

- mitigation
- owner
- resolved

## Match Strategy

Raise a medium signal when negative delivery terms appear. Include positive terms to help show whether mitigation language was also present.
