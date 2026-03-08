---
name: e2e-test-demo
description: End-to-end test demo Skill for validating KSkillHub platform's Skill creation, upload, parsing and display features. Use this Skill when performing smoke tests or regression tests on KSkillHub.
---

# E2E Test Demo

## Overview

This is a demo Skill for end-to-end testing of the KSkillHub platform. It contains a complete Skill package structure for validating:

1. `.skill` package upload and parsing
2. SKILL.md frontmatter (name, description) auto-extraction
3. SKILL.md body displayed as readme documentation
4. Package file structure (file_tree) extraction and display

## Usage

After uploading this .skill package to the KSkillHub platform, the platform should automatically:
- Extract the name as `e2e-test-demo`
- Extract description info
- Display this Markdown section as usage documentation

## Included Resources

### scripts/
- `example.py` - Example Python script

### references/
- `api_reference.md` - API reference documentation

### assets/
- `example_asset.txt` - Example resource file
