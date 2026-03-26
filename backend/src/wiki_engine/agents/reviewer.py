"""Reviewer agent — validates generated wiki pages against quality standards.

Phase 6 of the pipeline. Checks citation density, Mermaid syntax, file path
validity, and spot-checks claims against source code. Pages that fail get
flagged for re-generation.
"""

import json
import logging
import re
from pathlib import Path

from wiki_engine.llm.base import BaseLLM
from wiki_engine.pipeline.state import GeneratedPage, PipelineState
from wiki_engine.prompts.reviewer import REVIEWER_PROMPT, REVIEWER_SYSTEM

logger = logging.getLogger(__name__)


async def run_reviewer(
    state: PipelineState,
    llm: BaseLLM,
    page: GeneratedPage,
) -> GeneratedPage:
    """Validate a generated page and update its confidence score.

    Runs both programmatic checks (fast, deterministic) and LLM-based
    verification (slower, catches semantic issues).
    """
    # Phase 1: Programmatic validation (no LLM needed)
    errors = _programmatic_checks(state, page)

    # Phase 2: LLM-based validation (spot-check claims against source)
    if not errors or all("WARN" in e for e in errors):
        llm_result = await _llm_validation(state, llm, page)
        if llm_result:
            errors.extend(llm_result.get("errors", []))
            page.confidence_score = llm_result.get("confidence", 0.8)

    page.validation_errors = errors

    if any("FAIL" in e for e in errors):
        logger.warning("Page '%s' FAILED validation: %s", page.title, errors)
    else:
        logger.info(
            "Page '%s' passed validation (confidence: %.2f)",
            page.title, page.confidence_score,
        )

    return page


def _programmatic_checks(state: PipelineState, page: GeneratedPage) -> list[str]:
    """Fast, deterministic validation checks."""
    errors = []

    # 1. Citation density
    if page.citations_count < 5:
        errors.append(f"FAIL: Only {page.citations_count} citations (minimum 5)")

    # 2. Diagram count
    if page.diagrams_count < 3:
        errors.append(f"WARN: Only {page.diagrams_count} diagrams (target 3-5)")

    # 3. File path validation
    known_files = set(state.repo_analysis.files.keys()) if state.repo_analysis else set()
    for cited_file in page.source_files_cited:
        if cited_file not in known_files:
            # Check if it's a partial match (e.g., without leading src/)
            if not any(known.endswith(cited_file) for known in known_files):
                errors.append(f"WARN: Cited file not found in repo: {cited_file}")

    # 4. Word count / depth
    word_count = len(page.markdown.split())
    if word_count < 1000:
        errors.append(f"FAIL: Only {word_count} words (minimum 2000)")
    elif word_count < 2000:
        errors.append(f"WARN: Only {word_count} words (target 2000-4000)")

    # 5. Mermaid syntax basic checks
    mermaid_blocks = re.findall(r'```mermaid\n(.*?)```', page.markdown, re.DOTALL)
    for i, block in enumerate(mermaid_blocks):
        if "graph LR" in block:
            errors.append(f"WARN: Diagram {i+1} uses 'graph LR' (should be 'graph TD')")
        if "sequenceDiagram" in block and "participant" not in block:
            errors.append(f"WARN: Sequence diagram {i+1} missing participant declarations")

    # 6. Has <details> source file block
    if "<details>" not in page.markdown:
        errors.append("WARN: Missing <details> source file block at start of page")

    return errors


async def _llm_validation(
    state: PipelineState,
    llm: BaseLLM,
    page: GeneratedPage,
) -> dict | None:
    """LLM-based validation — spot-checks claims against source code."""
    # Read a subset of source files for verification
    source_content = ""
    for rel_path in page.source_files_cited[:5]:
        full_path = Path(state.repo_path) / rel_path
        if full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
                source_content += f"\n### {rel_path}\n```\n{numbered}\n```\n"
            except Exception:
                pass

    if not source_content:
        return None

    known_files = list(state.repo_analysis.files.keys()) if state.repo_analysis else []

    prompt = REVIEWER_PROMPT.format(
        page_title=page.title,
        page_content=page.markdown[:30_000],  # Trim for context
        source_files_content=source_content[:50_000],
        known_files=", ".join(known_files[:100]),
    )

    messages = [
        {"role": "system", "content": REVIEWER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    # Use the fast model (Haiku) for validation — it's a checking task
    response = await llm.generate(messages, max_tokens=4096, temperature=0.0)
    state.total_llm_calls += 1
    state.total_input_tokens += response.input_tokens
    state.total_output_tokens += response.output_tokens

    try:
        result = _parse_json_response(response.content)
        errors = []
        confidence = result.get("confidence_score", 0.8)

        # Extract validation failures
        for check_name in ["citation_density", "diagrams", "file_paths", "claim_check", "depth"]:
            check = result.get(check_name, {})
            if check.get("status") == "FAIL":
                errors.append(f"FAIL ({check_name}): {json.dumps(check)}")
            elif check.get("status") == "WARN":
                errors.append(f"WARN ({check_name}): {json.dumps(check)}")

        return {"errors": errors, "confidence": confidence}
    except Exception as e:
        logger.warning("Failed to parse reviewer response: %s", e)
        return None


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
