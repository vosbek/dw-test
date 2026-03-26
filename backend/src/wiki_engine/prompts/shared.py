"""Shared prompt constants — citation format, Mermaid rules, quality constraints.

These rules are injected into every agent prompt to enforce consistent quality.
"""

CITATION_RULES = """
## Citation Requirements (NON-NEGOTIABLE)

Every factual claim MUST cite the source file and line range it was derived from.
- Format: `Sources: [filename.ext:start_line-end_line]()`
- Multiple files: `Sources: [file1.ext:1-10](), [file2.ext:50-75]()`
- Whole file: `Sources: [dir/file.ext]()`
- You MUST cite AT LEAST 5 different source files per page
- Place citations at the end of paragraphs, under diagrams/tables, or after code snippets
- If you cannot point to specific code for a claim, prefix it with "Based on inference:"
- NEVER state something as fact without a source citation
"""

MERMAID_RULES = """
## Mermaid Diagram Requirements

Generate 3-5 Mermaid diagrams per page using at least 2 different diagram types:
- `graph TD` — architecture, component relationships, dependencies (ALWAYS top-down, NEVER LR)
- `sequenceDiagram` — API flows, request/response patterns (ALWAYS use `autonumber`)
- `classDiagram` — type hierarchies, class relationships
- `stateDiagram-v2` — lifecycle states, state machines
- `erDiagram` — data models, entity relationships
- `flowchart TD` — process pipelines, logic trees

Rules:
- CRITICAL: Use `graph TD` (top-down) — NEVER `graph LR` (left-right)
- Maximum node label width: 3-4 words
- Sequence diagrams: define ALL participants first, use correct arrow syntax:
  - `->>` solid with arrow (requests/calls)
  - `-->>` dotted with arrow (responses/returns)
  - `->>+` activate target, `-->>-` deactivate
  - Use `loop`, `alt`/`else`, `opt`, `par`/`and` for control flow
  - NEVER use flowchart-style labels on arrows
- Provide a brief explanation before each diagram
- Diagrams must reference actual source files/classes, not abstract labels
"""

DEPTH_RULES = """
## Depth and Quality Requirements

- Each page must be 2000-4000+ words of deep technical analysis (NOT surface-level summaries)
- Explain WHY before WHAT — purpose and design rationale before implementation details
- Start each page with a 30-second "at-a-glance" summary table
- Use tables instead of prose lists for structured information (components, configs, APIs)
- Progressive disclosure: big picture first, then granular details
- Trace actual code execution paths — NEVER infer from naming conventions
- Read real implementations — NEVER assume what code "probably does"
- Distinguish between verified facts (from code reading) and inferences
- If you haven't read a file, don't claim to know what it does
"""

ACCURACY_RULES = """
## Accuracy Requirements

- All information must be derived SOLELY from the provided source files
- Do NOT infer, invent, or use external knowledge about similar systems
- If information is not present in provided files, explicitly state its absence
- When context window limits prevent reading all code, state what you didn't analyze
- Prefer under-claiming to over-claiming: "This module appears to handle X based on [file:line]"
  rather than making definitive claims you aren't sure about
"""

PAGE_STRUCTURE = """
## Page Structure

Every page MUST follow this structure:
1. `<details>` block listing ALL source files used (minimum 5)
2. H1 heading with the page title
3. Introduction (1-2 paragraphs): purpose, scope, high-level overview
4. At-a-glance summary table
5. Detailed sections (H2/H3) with:
   - Architecture/component diagrams
   - Data flow explanations
   - Key functions/classes with signatures and purpose
   - Code snippets (under 20 lines) from source files
   - Source citations after every significant claim
6. Cross-references to related wiki pages
7. Summary/conclusion paragraph
"""

# Combined quality preamble injected into researcher and page-writer prompts
QUALITY_PREAMBLE = f"""
{ACCURACY_RULES}
{CITATION_RULES}
{DEPTH_RULES}
"""
