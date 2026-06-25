---
id: security.privacy_review_markers_present
ruleset: security
severity: medium
applies_to_presets:
  - architecture
  - risk
applies_to_sources:
  - confluence
  - jira
  - code
description: Retrieved evidence contains security or privacy review markers.
follow_up: Review access control, privacy and audit evidence for the affected feature or service.
---

# Security And Privacy Review Markers Present

## Negative Terms

- personal data
- pii
- token
- credential
- secret
- shared account
- manual access
- not encrypted

## Positive Terms

- permission
- role
- access control
- encryption
- audit
- least privilege

## Match Strategy

Raise a medium signal when security or privacy markers appear so they can be reviewed explicitly.
