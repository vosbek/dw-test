"""Wiki Researcher agent — 5-pass deep code analysis per wiki page.

Phase 3 of the pipeline. For each planned page, reads the actual source files
and produces structured research findings through 5 analytical passes:
structural, data flow, integration, pattern, and synthesis.
"""

import logging
from pathlib import Path

from wiki_engine.llm.base import BaseLLM
from wiki_engine.pipeline.state import PipelineState, ResearchFinding, WikiPagePlan
from wiki_engine.prompts.researcher import RESEARCHER_SYSTEM, RESEARCHER_PROMPT

logger = logging.getLogger(__name__)


async def run_wiki_researcher(
    state: PipelineState,
    llm: BaseLLM,
    page: WikiPagePlan,
) -> list[ResearchFinding]:
    """Run 5-pass research on source files for a single wiki page.

    Reads the actual source files mapped to this page, sends them to the LLM
    with the 5-pass research prompt, and returns structured findings.
    """
    # Read the actual source files
    source_content = _read_source_files(state.repo_path, page.relevant_files)

    if not source_content:
        logger.warning("No source files found for page '%s'", page.title)
        return [ResearchFinding(
            page_id=page.id,
            pass_name="error",
            content=f"No readable source files found among: {page.relevant_files}",
            cited_files=[],
            confidence=0.0,
        )]

    prompt = RESEARCHER_PROMPT.format(
        page_title=page.title,
        page_description=page.description,
        source_files_content=source_content,
    )

    messages = [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    # Use the analysis model (Sonnet) for research — good balance of quality and cost
    response = await llm.generate(messages, max_tokens=16384, temperature=0.1)
    state.total_llm_calls += 1
    state.total_input_tokens += response.input_tokens
    state.total_output_tokens += response.output_tokens

    # Parse the 5 passes from the response
    findings = _parse_research_passes(page.id, response.content, page.relevant_files)

    logger.info(
        "Researcher completed %d passes for '%s' (%d input tokens)",
        len(findings), page.title, response.input_tokens,
    )
    return findings


def _read_source_files(repo_path: str, file_paths: list[str]) -> str:
    """Read source files and format them for the LLM context.

    Returns formatted string with file contents and line numbers.
    """
    sections = []
    total_chars = 0
    max_chars = 500_000  # ~125K tokens — leave room for prompt + response

    for rel_path in file_paths:
        full_path = Path(repo_path) / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Add line numbers
        lines = content.splitlines()
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

        section = f"\n### File: `{rel_path}` ({len(lines)} lines)\n```\n{numbered}\n```\n"

        if total_chars + len(section) > max_chars:
            sections.append(f"\n### File: `{rel_path}` (TRUNCATED — file too large for context)\n")
            break

        sections.append(section)
        total_chars += len(section)

    return "\n".join(sections)


def _parse_research_passes(
    page_id: str, content: str, relevant_files: list[str]
) -> list[ResearchFinding]:
    """Parse the 5-pass research output into structured findings."""
    passes = {
        "structural": "",
        "data_flow": "",
        "integration": "",
        "pattern": "",
        "synthesis": "",
    }

    # Split by pass headers
    current_pass = None
    current_lines: list[str] = []

    for line in content.splitlines():
        lower = line.lower().strip()
        if "pass 1" in lower or "structural view" in lower:
            if current_pass:
                passes[current_pass] = "\n".join(current_lines)
            current_pass = "structural"
            current_lines = [line]
        elif "pass 2" in lower or "data flow" in lower:
            if current_pass:
                passes[current_pass] = "\n".join(current_lines)
            current_pass = "data_flow"
            current_lines = [line]
        elif "pass 3" in lower or "integration" in lower:
            if current_pass:
                passes[current_pass] = "\n".join(current_lines)
            current_pass = "integration"
            current_lines = [line]
        elif "pass 4" in lower or "pattern" in lower:
            if current_pass:
                passes[current_pass] = "\n".join(current_lines)
            current_pass = "pattern"
            current_lines = [line]
        elif "pass 5" in lower or "synthesis" in lower:
            if current_pass:
                passes[current_pass] = "\n".join(current_lines)
            current_pass = "synthesis"
            current_lines = [line]
        else:
            current_lines.append(line)

    # Capture the last pass
    if current_pass:
        passes[current_pass] = "\n".join(current_lines)

    # If parsing failed, treat the whole response as a single finding
    if not any(passes.values()):
        return [ResearchFinding(
            page_id=page_id,
            pass_name="combined",
            content=content,
            cited_files=relevant_files,
        )]

    findings = []
    for pass_name, pass_content in passes.items():
        if pass_content.strip():
            findings.append(ResearchFinding(
                page_id=page_id,
                pass_name=pass_name,
                content=pass_content,
                cited_files=relevant_files,
            ))

    return findings
