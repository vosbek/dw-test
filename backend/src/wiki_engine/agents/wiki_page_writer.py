"""Wiki Page Writer agent — generates DeepWiki-quality wiki pages.

Phase 4-5 of the pipeline. Takes research findings + source code and produces
complete wiki pages with Mermaid diagrams, source citations, and deep analysis.
"""

import logging
from pathlib import Path

from wiki_engine.llm.base import BaseLLM
from wiki_engine.pipeline.state import (
    GeneratedPage,
    PipelineState,
    ResearchFinding,
    WikiPagePlan,
)
from wiki_engine.prompts.page_writer import (
    CONTRIBUTOR_GUIDE_PROMPT,
    EXECUTIVE_GUIDE_PROMPT,
    PAGE_WRITER_PROMPT,
    PAGE_WRITER_SYSTEM,
    STAFF_ENGINEER_GUIDE_PROMPT,
)

logger = logging.getLogger(__name__)


async def run_page_writer(
    state: PipelineState,
    llm: BaseLLM,
    page: WikiPagePlan,
) -> GeneratedPage:
    """Generate a wiki page from research findings and source code.

    Uses the analysis model (Sonnet) for page generation.
    """
    # Gather research findings for this page
    findings = state.research_findings.get(page.id, [])
    research_text = "\n\n".join(f.content for f in findings) if findings else "No research findings available."

    # Read source files for direct reference
    source_content = _read_source_files(state.repo_path, page.relevant_files)

    # Build file list for the <details> block
    file_list = "\n".join(f"- `{f}`" for f in page.relevant_files)

    # Build related pages list
    related_pages = ""
    if state.catalogue:
        for p in state.catalogue.pages:
            if p.id in page.related_pages:
                related_pages += f"- [{p.title}](#{p.id})\n"

    prompt = PAGE_WRITER_PROMPT.format(
        page_title=page.title,
        page_description=page.description,
        research_findings=research_text,
        source_files_content=source_content,
        related_pages=related_pages or "None",
        file_list=file_list,
    )

    messages = [
        {"role": "system", "content": PAGE_WRITER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    response = await llm.generate(messages, max_tokens=16384, temperature=0.2)
    state.total_llm_calls += 1
    state.total_input_tokens += response.input_tokens
    state.total_output_tokens += response.output_tokens

    # Count quality metrics
    diagrams_count = response.content.count("```mermaid")
    citations_count = response.content.count("Sources:")
    files_cited = _extract_cited_files(response.content)

    generated = GeneratedPage(
        page_id=page.id,
        title=page.title,
        markdown=response.content,
        diagrams_count=diagrams_count,
        citations_count=citations_count,
        source_files_cited=files_cited,
    )

    logger.info(
        "Generated page '%s': %d words, %d diagrams, %d citations, %d files cited",
        page.title,
        len(response.content.split()),
        diagrams_count,
        citations_count,
        len(files_cited),
    )
    return generated


async def run_audience_guides(
    state: PipelineState,
    llm: BaseLLM,
) -> dict[str, GeneratedPage]:
    """Generate 4 audience-specific guides: contributor, staff engineer, executive, PM."""
    guides = {}

    # Combine all research findings for context
    all_research = "\n\n---\n\n".join(
        f"## {page_id}\n" + "\n".join(f.content for f in findings)
        for page_id, findings in state.research_findings.items()
    )

    # Read key source files (entry points, configs)
    key_files = []
    if state.repo_analysis:
        key_files = state.repo_analysis.entry_points[:5]
    source_content = _read_source_files(state.repo_path, key_files)

    guide_prompts = {
        "contributor-guide": ("Contributor Onboarding Guide", CONTRIBUTOR_GUIDE_PROMPT),
        "staff-engineer-guide": ("Staff Engineer Guide", STAFF_ENGINEER_GUIDE_PROMPT),
        "executive-guide": ("Executive Summary", EXECUTIVE_GUIDE_PROMPT),
    }

    for guide_id, (title, prompt_template) in guide_prompts.items():
        prompt = prompt_template.format(
            research_findings=all_research[:80_000],  # Trim for context limits
            source_files_content=source_content,
        )

        messages = [
            {"role": "system", "content": PAGE_WRITER_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        response = await llm.generate(messages, max_tokens=8192, temperature=0.2)
        state.total_llm_calls += 1
        state.total_input_tokens += response.input_tokens
        state.total_output_tokens += response.output_tokens

        guides[guide_id] = GeneratedPage(
            page_id=guide_id,
            title=title,
            markdown=response.content,
            diagrams_count=response.content.count("```mermaid"),
            citations_count=response.content.count("Sources:"),
            source_files_cited=_extract_cited_files(response.content),
        )
        logger.info("Generated guide: %s (%d words)", title, len(response.content.split()))

    return guides


def _read_source_files(repo_path: str, file_paths: list[str]) -> str:
    """Read source files with line numbers for LLM context."""
    sections = []
    total_chars = 0
    max_chars = 400_000

    for rel_path in file_paths:
        full_path = Path(repo_path) / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = content.splitlines()
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
        section = f"\n### File: `{rel_path}` ({len(lines)} lines)\n```\n{numbered}\n```\n"

        if total_chars + len(section) > max_chars:
            break
        sections.append(section)
        total_chars += len(section)

    return "\n".join(sections)


def _extract_cited_files(content: str) -> list[str]:
    """Extract unique file paths cited in the markdown content."""
    import re
    # Match patterns like [filename.ext:1-10]() or [dir/file.ext]()
    pattern = r'\[([^\]]+?\.(?:py|java|js|ts|jsx|tsx|cs|pl|pm)(?::\d+(?:-\d+)?)?)\]\(\)'
    matches = re.findall(pattern, content)
    # Strip line numbers to get just file paths
    files = set()
    for m in matches:
        file_path = m.split(":")[0]
        files.add(file_path)
    return sorted(files)
