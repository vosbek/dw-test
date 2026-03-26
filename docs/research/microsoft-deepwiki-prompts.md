# Microsoft deep-wiki Plugin: Architecture & Prompts (Reference)

Extracted from `microsoft/skills/.github/plugins/deep-wiki/` on 2026-03-26.
This is the more sophisticated approach — 8 phases, 3 specialized agents.

---

## Pipeline: 8 Phases

| Phase | Output | Purpose |
|-------|--------|---------|
| 0 | Repo context + citation format | Determine linked vs local citations |
| 1 | Directory scan + tech detection | Entry points, configs, architecture patterns |
| 2 | Hierarchical JSON catalogue | Wiki structure (max 4 levels, max 8 children/section) |
| 3 | Four onboarding guides | Contributor, staff engineer, executive, PM |
| 4 | Full wiki pages | Per-section docs with Mermaid, tables, cross-references |
| 5 | Validation + escaping | Fix Mermaid syntax, validate file paths, dark-mode |
| 6 | VitePress scaffold | Complete site with dark theme, click-to-zoom, sidebar |
| 7 | AGENTS.md + llms.txt | Machine-readable project summaries |

---

## 3 Specialized Agents

### wiki-architect
**Triggers**: Wiki creation, documentation generation, codebase mapping
**Pre-flight**: Resolve git remote URL, determine citation format
**Output**: JSON catalogue with 4 mandatory onboarding guides + standard sections
**Constraints**:
- Max 4 nesting levels, 8 children per section
- Small repos (<10 files): Getting Started + onboarding only
- Every section must cite actual repository files
- Titles derived from real codebase content

**Audience guides**:
- Contributor Guide: Progressive learning (foundations -> architecture -> hands-on)
- Staff Engineer Guide: Dense, opinionated, system diagrams, tradeoffs
- Executive Guide: Risk, capability, investment (no code)
- PM Guide: User journeys, features (zero jargon)

### wiki-researcher
**Triggers**: Deep investigation, code path tracing, architectural analysis
**Pre-flight**: Resolve repo context for citations

**5 Analytical Passes**:
1. **Structural view** — map components and entry points with architecture diagrams
2. **Data flow view** — trace state and transformations with sequence/state diagrams
3. **Integration view** — external dependencies and API contracts
4. **Pattern view** — design patterns, technical debt, and risks
5. **Synthesis view** — actionable recommendations with impact rankings

**Non-negotiable principles**:
- Trace actual code execution paths — never infer from naming conventions
- Read real implementations — avoid assumptions about what code "probably does"
- Follow complete chains of dependencies and function calls
- Distinguish between verified facts and inferences explicitly
- No diagram-based analysis without corresponding code evidence
- No pattern assumptions without verification in actual code
- Claims must be grounded: file paths, line numbers, call chains required

**Evidence requirements per finding**:
- Clear statement
- File/line citations
- Implications explained
- Confidence level assessed
- Open questions flagged

### wiki-page-writer
**Triggers**: Component/system documentation, technical deep-dives, catalogue content

**Non-negotiable quality standards**:
- Code tracing: Read actual implementations, never infer from filenames
- Every factual claim requires source evidence with file path + function/class name
- Citation format:
  - Remote: `[src/file.ts:42](REPO_URL/blob/BRANCH/src/file.ts#L42)`
  - Local: `(src/file.ts:42)`
- Minimum 5 different files cited per page
- Source comments below Mermaid diagrams: `<!-- Sources: file_path:line, ... -->`

**Diagram requirements (3-5 per page, scaled by scope)**:
- Minimum 2 different diagram types
- Types: graph TB/LR, sequenceDiagram, classDiagram, stateDiagram-v2, erDiagram, flowchart
- Dark-mode palette: fills `#2d333b`, borders `#6d5dfc`, text `#e6edf3`
- All sequence diagrams must use `autonumber`

**Page structure**:
- VitePress frontmatter (title + description)
- Overview (WHY first) -> Architecture -> Components -> Data Flow -> Implementation
- Aggressive use of summary tables with linked citations
- Progressive disclosure: big picture before granular details
- Cross-references to related wiki pages with relative markdown links
- Related Pages section at conclusion

---

## Key Quality Rules (from generate.md)

**Citation discipline**: "Every architectural claim needs a source — file path + function/class name."

**Content structure**: Pages open with "why this exists" overview + 30-second at-a-glance table, then progress through implementation details with tables preferred over prose lists.

**Critical guards**:
- Escape bare generics (e.g., `Task<string>`) in prose
- Replace `<br/>` with `<br>` in Mermaid for Vue compiler compatibility
- Validate all file path citations exist in repository

---

## Single Page Generation (page.md)

**Three mandatory phases**:
1. **Strategic Planning** — clarify scope, audience, documentation budget based on file count
2. **Deep Code Analysis** — trace actual implementation paths, not assumptions
3. **Document Generation** — structure with frontmatter, overview, diagrams, tables, citations

**Non-negotiable depth standards**:
- Trace code paths completely (function A -> B -> C)
- Every claim requires a source file and line number
- Distinguish facts (from code inspection) from inferences
- Explain WHY before WHAT
- No hand-waving or guessing
