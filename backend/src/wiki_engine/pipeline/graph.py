"""LangGraph pipeline — orchestrates the 8-phase wiki generation workflow.

Phase 0-1: Repo scanning (deterministic)
Phase 2: Wiki architect (LLM)
Phase 3: Wiki researcher — 5-pass analysis per page (LLM)
Phase 4: Wiki page writer (LLM)
Phase 5: Audience guides (LLM)
Phase 6: Reviewer/validator (LLM + programmatic)
Phase 7: Assembly + output
"""

import asyncio
import logging
from pathlib import Path

from wiki_engine.agents.reviewer import run_reviewer
from wiki_engine.agents.wiki_architect import run_wiki_architect
from wiki_engine.agents.wiki_page_writer import run_audience_guides, run_page_writer
from wiki_engine.agents.wiki_researcher import run_wiki_researcher
from wiki_engine.ingestion.repo_scanner import (
    build_dependency_graph,
    clone_repo,
    get_file_tree,
    get_readme,
    scan_repo,
)
from wiki_engine.llm.bedrock import ModelRouter
from wiki_engine.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


async def run_pipeline(repo_url: str, branch: str | None = None) -> PipelineState:
    """Run the full wiki generation pipeline on a repository.

    This is the main entry point. It orchestrates all 8 phases sequentially,
    with Phase 3 (research) parallelized across pages.
    """
    state = PipelineState(repo_url=repo_url, branch=branch)
    router = ModelRouter()

    try:
        # Phase 0-1: Repo scanning (deterministic — no LLM)
        logger.info("Phase 0-1: Scanning repository...")
        state = await _phase_scan(state, repo_url, branch)

        # Phase 2: Wiki architect (LLM plans the structure)
        logger.info("Phase 2: Planning wiki structure...")
        state = await run_wiki_architect(state, router.fast)

        if not state.catalogue or not state.catalogue.pages:
            state.errors.append("Architect produced no pages")
            return state

        logger.info(
            "Planned %d pages: %s",
            len(state.catalogue.pages),
            [p.title for p in state.catalogue.pages],
        )

        # Phase 3: Research — 5-pass analysis per page (parallelized)
        logger.info("Phase 3: Deep code research (%d pages)...", len(state.catalogue.pages))
        research_tasks = [
            run_wiki_researcher(state, router.analysis, page)
            for page in state.catalogue.pages
        ]
        results = await asyncio.gather(*research_tasks, return_exceptions=True)
        for page, result in zip(state.catalogue.pages, results):
            if isinstance(result, Exception):
                logger.error("Research failed for '%s': %s", page.title, result)
                state.errors.append(f"Research failed for {page.title}: {result}")
            else:
                state.research_findings[page.id] = result

        # Phase 4: Page generation (sequential — each page can be large)
        logger.info("Phase 4: Generating wiki pages...")
        for page in state.catalogue.pages:
            if page.id not in state.research_findings:
                continue
            try:
                generated = await run_page_writer(state, router.analysis, page)
                state.generated_pages[generated.page_id] = generated
            except Exception as e:
                logger.error("Page generation failed for '%s': %s", page.title, e)
                state.errors.append(f"Generation failed for {page.title}: {e}")

        # Phase 5: Audience-specific guides
        logger.info("Phase 5: Generating audience guides...")
        try:
            guides = await run_audience_guides(state, router.analysis)
            state.generated_pages.update(guides)
        except Exception as e:
            logger.error("Audience guide generation failed: %s", e)
            state.errors.append(f"Guide generation failed: {e}")

        # Phase 6: Validation
        logger.info("Phase 6: Validating pages...")
        for page_id, page in list(state.generated_pages.items()):
            try:
                validated = await run_reviewer(state, router.fast, page)
                state.generated_pages[page_id] = validated
            except Exception as e:
                logger.error("Validation failed for '%s': %s", page.title, e)

        state.validated = True

        # Phase 7: Assembly
        logger.info("Phase 7: Assembling wiki...")
        state = _phase_assemble(state)

        logger.info(
            "Pipeline complete: %d pages generated, %d LLM calls, %d input tokens, %d output tokens",
            len(state.generated_pages),
            state.total_llm_calls,
            state.total_input_tokens,
            state.total_output_tokens,
        )

    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        state.errors.append(f"Pipeline error: {e}")

    return state


async def _phase_scan(state: PipelineState, repo_url: str, branch: str | None) -> PipelineState:
    """Phase 0-1: Clone repo, scan files, build dependency graph."""
    # Clone or use local path
    if repo_url.startswith("http") or repo_url.startswith("git@"):
        repo_path = clone_repo(repo_url, branch)
    else:
        repo_path = Path(repo_url)

    state.repo_path = str(repo_path)
    state.file_tree = get_file_tree(repo_path)
    state.readme = get_readme(repo_path)
    state.repo_analysis = scan_repo(repo_path)
    state.dependency_graph = build_dependency_graph(state.repo_analysis)

    logger.info(
        "Scanned: %d files, %d LOC, %d dependency edges",
        len(state.repo_analysis.files),
        state.repo_analysis.total_loc,
        len(state.dependency_graph.edges),
    )
    return state


def _phase_assemble(state: PipelineState) -> PipelineState:
    """Phase 7: Assemble final wiki output."""
    # Build table of contents
    toc_lines = ["# Table of Contents\n"]
    if state.catalogue:
        for section in state.catalogue.sections:
            toc_lines.append(f"\n## {section.title}\n")
            for page_id in section.pages:
                page = state.generated_pages.get(page_id)
                if page:
                    toc_lines.append(f"- [{page.title}](#{page_id})")

    # Add audience guides
    guide_ids = ["contributor-guide", "staff-engineer-guide", "executive-guide"]
    guides = [state.generated_pages.get(gid) for gid in guide_ids if gid in state.generated_pages]
    if guides:
        toc_lines.append("\n## Guides\n")
        for guide in guides:
            toc_lines.append(f"- [{guide.title}](#{guide.page_id})")

    # Store ToC as a special page
    from wiki_engine.pipeline.state import GeneratedPage
    state.generated_pages["_toc"] = GeneratedPage(
        page_id="_toc",
        title="Table of Contents",
        markdown="\n".join(toc_lines),
        diagrams_count=0,
        citations_count=0,
        source_files_cited=[],
    )

    return state
