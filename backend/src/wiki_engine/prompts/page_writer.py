"""Wiki Page Writer prompt — generates DeepWiki-quality wiki pages.

Takes research findings + source code and produces a complete wiki page with
Mermaid diagrams, source citations, and deep technical analysis.
"""

from wiki_engine.prompts.shared import (
    CITATION_RULES,
    DEPTH_RULES,
    MERMAID_RULES,
    PAGE_STRUCTURE,
)

PAGE_WRITER_SYSTEM = """You are an expert technical writer and software architect.
You produce comprehensive, accurate technical wiki pages in Markdown format.
Every claim is grounded in source code with file:line citations. You explain
WHY before WHAT, use Mermaid diagrams extensively, and write for senior engineers
who need to understand unfamiliar codebases quickly."""

PAGE_WRITER_PROMPT = """## Task

Generate a comprehensive technical wiki page for:
**"{page_title}"**

Page description: {page_description}

{PAGE_STRUCTURE}
{MERMAID_RULES}
{CITATION_RULES}
{DEPTH_RULES}

## Research Findings

The wiki-researcher has already analyzed the source code. Use these findings as
your primary input — they contain verified facts with file:line citations:

{research_findings}

## Source Files

The actual source code is provided below for reference. Cite specific lines.

{source_files_content}

## Related Pages

These other wiki pages exist for cross-referencing:
{related_pages}

## Generation Instructions

1. Start with the `<details>` block listing ALL source files (minimum 5):

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:
{file_list}
</details>

2. Then H1 heading: `# {page_title}`

3. Write 2000-4000+ words of deep technical content following the page structure above.

4. Generate 3-5 Mermaid diagrams using at least 2 different types.

5. Cite sources after EVERY significant claim using the citation format.

6. End with cross-references to related wiki pages.

CRITICAL REMINDERS:
- Ground EVERY claim in the provided source files — no hand-waving
- Trace actual code paths (function A calls B which calls C) — never guess
- Use tables for structured data (components, configs, APIs)
- Explain WHY the code is designed this way, not just WHAT it does
- Minimum 5 different source files cited throughout the page
- Minimum 3 Mermaid diagrams, minimum 2 different diagram types
""".replace("{PAGE_STRUCTURE}", PAGE_STRUCTURE).replace(
    "{MERMAID_RULES}", MERMAID_RULES
).replace("{CITATION_RULES}", CITATION_RULES).replace("{DEPTH_RULES}", DEPTH_RULES)

# Audience-specific guide prompts

CONTRIBUTOR_GUIDE_PROMPT = """## Task

Generate a **Contributor Onboarding Guide** (1000-2500 words) for this codebase.

Target audience: A new developer joining the team who needs to get productive quickly.

Structure:
1. Language & framework foundations — what you need to know before diving in
2. Codebase architecture — the big picture, key modules, how they connect
3. Getting started — setup, running locally, running tests
4. Making your first change — where to look, common patterns, code conventions
5. Key files to understand first — the 10 most important files and why

{research_findings}

{source_files_content}

Write for a developer who is technically competent but unfamiliar with this specific codebase.
Include Mermaid diagrams for architecture overview. Cite file:line for all claims.
"""

STAFF_ENGINEER_GUIDE_PROMPT = """## Task

Generate a **Staff Engineer Guide** (800-1200 words) for this codebase.

Target audience: A staff+ engineer evaluating the system's architecture.

Structure:
1. Architecture overview — key design decisions and trade-offs
2. System diagram — component relationships and data flow
3. Technical debt and risks — what's fragile, what needs attention
4. Scalability considerations — bottlenecks, growth limitations
5. Recommended improvements — prioritized by impact

{research_findings}

{source_files_content}

Be dense and opinionated. Include pseudocode where it clarifies. Cite file:line for all claims.
"""

EXECUTIVE_GUIDE_PROMPT = """## Task

Generate an **Executive Summary** (400-800 words) for this codebase.

Target audience: Engineering leadership who need to understand capability and risk.

Structure:
1. What it does — business purpose in plain language
2. Technology stack — key technologies and why they were chosen
3. Health assessment — overall code quality, test coverage, documentation state
4. Risk factors — dependencies, technical debt, bus factor
5. Investment areas — where additional engineering effort would have highest ROI

{research_findings}

NO code. NO jargon. Service-level diagrams only. Focus on business context.
"""
