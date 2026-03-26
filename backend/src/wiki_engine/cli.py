"""CLI entry point — run the wiki generation pipeline from the command line."""

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

console = Console()


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


@click.group()
def main():
    """Wiki Engine — AI-powered codebase documentation."""
    pass


@main.command()
@click.argument("repo", type=str)
@click.option("--branch", "-b", default=None, help="Git branch to analyze")
@click.option("--output", "-o", default="./wiki-output", help="Output directory")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def generate(repo: str, branch: str | None, output: str, verbose: bool):
    """Generate a wiki for a repository.

    REPO can be a GitHub URL or a local path.

    Examples:
        wiki-engine generate https://github.com/pallets/flask
        wiki-engine generate ./my-project --output ./docs
        wiki-engine generate https://github.com/spring-projects/spring-boot -b main
    """
    _setup_logging(verbose)

    console.print(f"\n[bold]Wiki Engine[/bold] — Generating wiki for [cyan]{repo}[/cyan]\n")

    from wiki_engine.pipeline.graph import run_pipeline

    state = asyncio.run(run_pipeline(repo, branch))

    # Output results
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Write each page as a markdown file
    for page_id, page in state.generated_pages.items():
        if page_id == "_toc":
            file_name = "index.md"
        elif page_id.startswith("page-"):
            file_name = f"{page_id}.md"
        else:
            file_name = f"{page_id}.md"

        file_path = output_path / file_name
        file_path.write_text(page.markdown, encoding="utf-8")

    # Print summary
    console.print("\n[bold green]Wiki generation complete![/bold green]\n")

    table = Table(title="Generation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Pages generated", str(len(state.generated_pages)))
    table.add_row("Total LLM calls", str(state.total_llm_calls))
    table.add_row("Input tokens", f"{state.total_input_tokens:,}")
    table.add_row("Output tokens", f"{state.total_output_tokens:,}")
    table.add_row("Output directory", str(output_path.absolute()))

    if state.errors:
        table.add_row("Errors", str(len(state.errors)))

    console.print(table)

    # Print validation summary
    validated_pages = [
        p for p in state.generated_pages.values()
        if p.validation_errors
    ]
    if validated_pages:
        console.print("\n[bold]Validation Results:[/bold]")
        for page in validated_pages:
            status = "[red]FAIL[/red]" if any("FAIL" in e for e in page.validation_errors) else "[yellow]WARN[/yellow]"
            console.print(f"  {status} {page.title}: {', '.join(page.validation_errors[:3])}")

    pages_without_issues = [
        p for p in state.generated_pages.values()
        if not p.validation_errors and p.page_id != "_toc"
    ]
    if pages_without_issues:
        console.print(f"\n  [green]PASS[/green] {len(pages_without_issues)} pages passed all checks")

    if state.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in state.errors:
            console.print(f"  [red]•[/red] {error}")

    console.print(f"\n[dim]Output written to {output_path.absolute()}[/dim]\n")


@main.command()
@click.argument("repo", type=str)
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def scan(repo: str, verbose: bool):
    """Scan a repository without generating a wiki (useful for testing parser)."""
    _setup_logging(verbose)

    from wiki_engine.ingestion.repo_scanner import (
        build_dependency_graph,
        scan_repo,
    )

    repo_path = Path(repo)
    if not repo_path.exists():
        console.print(f"[red]Path not found: {repo}[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Scanning[/bold] [cyan]{repo}[/cyan]...\n")

    analysis = scan_repo(repo_path)
    graph = build_dependency_graph(analysis)

    table = Table(title="Scan Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total files", str(len(analysis.files)))
    table.add_row("Total LOC", f"{analysis.total_loc:,}")
    table.add_row("Languages", ", ".join(f"{l.value}: {c}" for l, c in analysis.languages.items()))
    table.add_row("Frameworks", ", ".join(analysis.frameworks) or "None")
    table.add_row("Build systems", ", ".join(analysis.build_systems) or "None")
    table.add_row("Entry points", ", ".join(analysis.entry_points[:5]) or "None")
    table.add_row("Dependency edges", str(len(graph.edges)))

    # Count symbols
    total_classes = sum(
        1 for f in analysis.files.values()
        for s in f.symbols if s.kind.value == "class"
    )
    total_functions = sum(
        1 for f in analysis.files.values()
        for s in f.symbols if s.kind.value in ("function", "method")
    )
    table.add_row("Classes/interfaces", str(total_classes))
    table.add_row("Functions/methods", str(total_functions))

    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
