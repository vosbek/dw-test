"""Wiki Architect agent — plans the wiki structure from repo analysis.

Phase 2 of the pipeline. Takes repo analysis (file tree, README, dependency graph,
symbol tables) and produces a WikiCatalogue defining the page hierarchy.
"""

import json
import logging

from wiki_engine.ingestion.models import RepoAnalysis, DependencyGraph
from wiki_engine.llm.base import BaseLLM
from wiki_engine.pipeline.state import PipelineState, WikiCatalogue, WikiPagePlan, WikiSection
from wiki_engine.prompts.architect import ARCHITECT_SYSTEM, ARCHITECT_PROMPT

logger = logging.getLogger(__name__)


async def run_wiki_architect(state: PipelineState, llm: BaseLLM) -> PipelineState:
    """Plan the wiki structure based on repo analysis.

    Sends the file tree, README, and code analysis summary to the LLM.
    Returns a WikiCatalogue with planned pages and sections.
    """
    analysis: RepoAnalysis = state.repo_analysis
    dep_graph: DependencyGraph = state.dependency_graph

    # Build the prompt context
    languages = ", ".join(f"{lang.value}: {count} files" for lang, count in analysis.languages.items())
    key_symbols = _get_key_symbols(analysis, limit=30)
    most_imported = _get_most_imported(analysis, dep_graph, limit=10)
    most_dependent = _get_most_dependent(analysis, dep_graph, limit=10)

    prompt = ARCHITECT_PROMPT.format(
        repo_name=state.repo_url or state.repo_path,
        file_tree=state.file_tree,
        readme=state.readme,
        languages=languages,
        total_files=len(analysis.files),
        total_loc=analysis.total_loc,
        frameworks=", ".join(analysis.frameworks) or "None detected",
        build_systems=", ".join(analysis.build_systems) or "None detected",
        entry_points=", ".join(analysis.entry_points[:10]) or "None detected",
        key_symbols=key_symbols,
        most_imported=most_imported,
        most_dependent=most_dependent,
    )

    messages = [
        {"role": "system", "content": ARCHITECT_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    response = await llm.generate(messages, max_tokens=8192, temperature=0.1)
    state.total_llm_calls += 1
    state.total_input_tokens += response.input_tokens
    state.total_output_tokens += response.output_tokens

    # Parse JSON response
    try:
        catalogue_data = _parse_json_response(response.content)
        state.catalogue = _build_catalogue(catalogue_data)
        logger.info(
            "Wiki architect planned %d pages in %d sections",
            len(state.catalogue.pages),
            len(state.catalogue.sections),
        )
    except Exception as e:
        logger.error("Failed to parse architect response: %s", e)
        state.errors.append(f"Architect JSON parse error: {e}")
        # Fallback: create a basic structure from the analysis
        state.catalogue = _fallback_catalogue(analysis)

    return state


def _get_key_symbols(analysis: RepoAnalysis, limit: int) -> str:
    """Get the most important symbols (classes, interfaces) for the prompt."""
    symbols = []
    for file_analysis in analysis.files.values():
        for sym in file_analysis.symbols:
            if sym.kind.value in ("class", "interface", "enum"):
                symbols.append(f"  - {sym.signature} ({sym.file_path}:{sym.start_line})")
    return "\n".join(symbols[:limit]) or "  None extracted"


def _get_most_imported(analysis: RepoAnalysis, graph: DependencyGraph, limit: int) -> str:
    """Files that are depended on by the most other files."""
    incoming: dict[str, int] = {}
    for edge in graph.edges:
        incoming[edge.target] = incoming.get(edge.target, 0) + edge.weight
    sorted_files = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:limit]
    return "\n".join(f"  - {f} ({count} dependents)" for f, count in sorted_files) or "  None"


def _get_most_dependent(analysis: RepoAnalysis, graph: DependencyGraph, limit: int) -> str:
    """Files that import the most other files."""
    outgoing: dict[str, int] = {}
    for edge in graph.edges:
        outgoing[edge.source] = outgoing.get(edge.source, 0) + edge.weight
    sorted_files = sorted(outgoing.items(), key=lambda x: x[1], reverse=True)[:limit]
    return "\n".join(f"  - {f} ({count} dependencies)" for f, count in sorted_files) or "  None"


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    # Strip markdown code fences if present
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _build_catalogue(data: dict) -> WikiCatalogue:
    """Build a WikiCatalogue from parsed JSON."""
    sections = []
    for s in data.get("sections", []):
        sections.append(WikiSection(
            id=s["id"],
            title=s["title"],
            pages=s.get("pages", []),
            subsections=s.get("subsections", []),
        ))

    pages = []
    for p in data.get("pages", []):
        pages.append(WikiPagePlan(
            id=p["id"],
            title=p["title"],
            description=p.get("description", ""),
            relevant_files=p.get("relevant_files", []),
            related_pages=p.get("related_pages", []),
            importance=p.get("importance", "medium"),
            parent_section=p.get("parent_section"),
        ))

    return WikiCatalogue(
        title=data.get("title", "Wiki"),
        description=data.get("description", ""),
        sections=sections,
        pages=pages,
    )


def _fallback_catalogue(analysis: RepoAnalysis) -> WikiCatalogue:
    """Create a basic catalogue when the LLM response fails to parse."""
    pages = [
        WikiPagePlan(
            id="page-overview",
            title="Overview",
            description="Project overview and architecture",
            relevant_files=list(analysis.files.keys())[:10],
            related_pages=[],
            importance="high",
        )
    ]
    sections = [
        WikiSection(id="section-1", title="Overview", pages=["page-overview"]),
    ]
    return WikiCatalogue(
        title="Wiki",
        description="Auto-generated documentation",
        sections=sections,
        pages=pages,
    )
