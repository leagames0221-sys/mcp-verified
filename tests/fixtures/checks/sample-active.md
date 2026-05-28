---
title: Sample Active Credential Check
version: 1.0
date: 2026-05-29
tags: [security, credentials, sample]
aliases: [sample-credential-check]
status: active
priority: high
cwe: [798, 200]
cwe-primary: 798
vulnerability-db: []
---

## Purpose

A minimal active check used by the loader unit tests.

## Why This Matters

Hard-coded credentials in MCP server source are routinely committed to
public repositories; the loader must be able to consume this kind of
file and surface it to the audit pipeline.

## For AI Assistants: Automated Analysis

Scan for environment-variable assignments, hard-coded tokens, and
config files containing secrets.

## For Humans: Manual Assessment Steps

Review credential handling code paths for safe storage and minimal
privilege.

## Implementation Examples

```python
# Good
token = os.environ["SERVICE_TOKEN"]

# Bad
token = "sk-abcdef0123456789"
```
