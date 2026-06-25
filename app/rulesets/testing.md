---
id: testing.quality_terms_missing
ruleset: testing
severity: medium
applies_to_presets:
  - delivery
  - performance
  - risk
applies_to_sources:
  - confluence
  - jira
  - code
description: Testing and quality terms were not found in retrieved evidence.
follow_up: Ask where test, UAT, regression or performance validation evidence is recorded.
---

# Testing And Quality Terms Missing

## Required Any Terms

- test
- tested
- uat
- acceptance criteria
- integration test
- regression
- performance test
- load test

## Negative Terms

- untested
- no test
- no uat
- manual only

## Match Strategy

Raise a medium signal when implementation or delivery evidence exists but testing and quality terms are missing.
