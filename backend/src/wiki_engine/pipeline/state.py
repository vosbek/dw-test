"""Pipeline state schema — passed between LangGraph nodes."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WikiPagePlan:
    """A planned wiki page from the architect."""

    id: str
    title: str
    description: str
    relevant_files: list[str]
    related_pages: list[str]
    importance: str = "medium"  # high, medium, low
    parent_section: str | None = None


@dataclass
class WikiSection:
    """A section within the wiki catalogue."""

    id: str
    title: str
    pages: list[str]  # page IDs
    subsections: list[str] = field(default_factory=list)  # section IDs


@dataclass
class WikiCatalogue:
    """The wiki structure planned by the architect."""

    title: str
    description: str
    sections: list[WikiSection]
    pages: list[WikiPagePlan]


@dataclass
class ResearchFinding:
    """A research finding from the wiki-researcher."""

    page_id: str
    pass_name: str  # structural, data_flow, integration, pattern, synthesis
    content: str
    cited_files: list[str]
    confidence: float = 1.0


@dataclass
class GeneratedPage:
    """A generated wiki page."""

    page_id: str
    title: str
    markdown: str
    diagrams_count: int
    citations_count: int
    source_files_cited: list[str]
    confidence_score: float = 1.0
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class PipelineState:
    """Full state passed through the LangGraph pipeline.

    Each node reads what it needs and writes its outputs.
    """

    # Input
    repo_url: str = ""
    repo_path: str = ""
    branch: str | None = None

    # Phase 0-1: Repo context
    file_tree: str = ""
    readme: str = ""
    repo_analysis: Any = None  # RepoAnalysis (avoid circular import)
    dependency_graph: Any = None  # DependencyGraph

    # Phase 2: Wiki structure
    catalogue: WikiCatalogue | None = None

    # Phase 3: Research
    research_findings: dict[str, list[ResearchFinding]] = field(default_factory=dict)

    # Phase 4-5: Generated pages
    generated_pages: dict[str, GeneratedPage] = field(default_factory=dict)

    # Phase 6: Validation results
    validated: bool = False
    validation_report: str = ""

    # Metadata
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    errors: list[str] = field(default_factory=list)
