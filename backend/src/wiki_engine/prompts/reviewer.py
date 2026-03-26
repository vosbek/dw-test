"""Reviewer/Validator prompt — quality gate for generated wiki pages.

Checks: Mermaid syntax, citation density, file path validity, claim accuracy.
Pages that fail validation get re-generated with corrective context.
"""

REVIEWER_SYSTEM = """You are a meticulous technical documentation reviewer.
You verify that wiki pages are accurate, well-cited, and follow quality standards.
You check every claim against actual source code and flag any issues."""

REVIEWER_PROMPT = """## Validation Task

Review the following wiki page for accuracy and quality.

### Page Title: {page_title}

### Generated Content:
{page_content}

### Source Files Available:
{source_files_content}

## Validation Checks

Perform each check and report findings:

### 1. Citation Density
- Count the number of unique source files cited
- PASS: 5+ different files cited. FAIL: fewer than 5.
- List all cited files.

### 2. Mermaid Diagram Quality
- Count the number of Mermaid diagrams
- PASS: 3+ diagrams with 2+ different types. FAIL: fewer.
- Check each diagram for syntax errors:
  - `graph TD` not `graph LR`
  - `sequenceDiagram` participants defined before use
  - No flowchart-style labels on sequence arrows
  - Proper arrow syntax (->> not -->)
- List any syntax issues found.

### 3. File Path Validation
- Check each cited file path against the repository file list: {known_files}
- PASS: all cited files exist. FAIL: any cited file doesn't exist.
- List any invalid file paths.

### 4. Claim Spot-Check
- Select 5 specific factual claims from the page
- For each claim, verify it against the actual source code provided
- PASS: all 5 claims are accurate. WARN: 1-2 inaccuracies. FAIL: 3+ inaccuracies.
- For each checked claim, state: the claim, the source evidence, PASS/FAIL.

### 5. Depth Check
- Estimate word count (approximate is fine)
- PASS: 2000+ words. WARN: 1000-2000. FAIL: under 1000.
- Does the page explain WHY, not just WHAT?
- Does it use tables for structured data?

## Output Format

```json
{{
  "overall": "PASS" | "WARN" | "FAIL",
  "confidence_score": 0.0-1.0,
  "citation_density": {{"status": "PASS|FAIL", "unique_files_cited": N, "files": [...]}},
  "diagrams": {{"status": "PASS|FAIL", "count": N, "types": [...], "syntax_issues": [...]}},
  "file_paths": {{"status": "PASS|FAIL", "invalid_paths": [...]}},
  "claim_check": {{"status": "PASS|WARN|FAIL", "checks": [...]}},
  "depth": {{"status": "PASS|WARN|FAIL", "estimated_words": N}},
  "suggested_fixes": ["list of specific things to fix if re-generating"]
}}
```

Return ONLY valid JSON.
"""
