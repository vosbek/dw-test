"""Wiki Architect prompt — plans the wiki structure from repo analysis."""

ARCHITECT_SYSTEM = """You are a senior software architect and technical documentation strategist.
Your task is to analyze a codebase and plan the structure of a comprehensive technical wiki.
You produce a JSON catalogue defining the wiki's hierarchical page structure."""

ARCHITECT_PROMPT = """Analyze this repository and create a wiki structure for it.

## Repository: {repo_name}

### File Tree
<file_tree>
{file_tree}
</file_tree>

### README
<readme>
{readme}
</readme>

### Code Analysis Summary
- **Languages**: {languages}
- **Total files**: {total_files}
- **Total lines of code**: {total_loc}
- **Frameworks detected**: {frameworks}
- **Build systems**: {build_systems}
- **Entry points**: {entry_points}
- **Key classes/interfaces**: {key_symbols}

### Dependency Insights
- **Most-imported files** (highest dependency count): {most_imported}
- **Most-dependent files** (import the most): {most_dependent}

## Instructions

Create a comprehensive wiki structure with 8-12 pages organized into logical sections.

### Section Guidelines
- **Overview**: General project purpose, architecture summary, tech stack
- **System Architecture**: How the system is designed, key design patterns, component relationships
- **Core Components**: Deep dives into the most important modules/packages
- **Data Management**: Database schema, data flow, state management, API contracts
- **Key Workflows**: Request handling, processing pipelines, business logic flows
- **Configuration & Deployment**: Build system, config management, environment setup
- **Testing & Quality**: Test infrastructure, testing patterns, CI/CD
- **Extensibility**: Plugin systems, customization points, extension patterns

Adapt sections to what the codebase actually contains — skip sections that don't apply.

### For Each Page
- Assign the specific source files that are most relevant (use the dependency analysis to identify related files)
- Each page should reference 5-15 source files
- High-importance pages cover core functionality; low-importance pages cover peripheral features
- Link related pages to enable cross-referencing

### Constraints
- Maximum 4 nesting levels
- Maximum 8 children per section
- Every page must cite actual repository files
- Page titles must be derived from actual codebase content, not generic names

Return your analysis as valid JSON with this exact structure:

```json
{{
  "title": "Wiki title",
  "description": "Brief repo description",
  "sections": [
    {{
      "id": "section-1",
      "title": "Section Title",
      "pages": ["page-1", "page-2"],
      "subsections": []
    }}
  ],
  "pages": [
    {{
      "id": "page-1",
      "title": "Page Title",
      "description": "What this page covers",
      "importance": "high",
      "relevant_files": ["src/main.py", "src/core/engine.py"],
      "related_pages": ["page-2"],
      "parent_section": "section-1"
    }}
  ]
}}
```

Return ONLY valid JSON. No markdown code blocks. No explanation text.
"""
