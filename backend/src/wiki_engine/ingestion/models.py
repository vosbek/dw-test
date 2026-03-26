"""Data models for code ingestion — symbols, files, dependencies."""

from dataclasses import dataclass, field
from enum import Enum


class SymbolKind(Enum):
    """Kind of code symbol extracted by AST parsing."""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    ENUM = "enum"
    MODULE = "module"
    CONSTANT = "constant"
    IMPORT = "import"


class Language(Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    PERL = "perl"
    CSHARP = "csharp"
    UNKNOWN = "unknown"


LANGUAGE_EXTENSIONS: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".java": Language.JAVA,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".pl": Language.PERL,
    ".pm": Language.PERL,
    ".cs": Language.CSHARP,
}


@dataclass
class Symbol:
    """A code symbol extracted from AST parsing."""

    name: str
    kind: SymbolKind
    file_path: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    parent: str | None = None  # e.g., class name for methods


@dataclass
class ImportRef:
    """An import/include reference."""

    source_file: str
    imported_name: str
    imported_from: str  # module/package path
    line: int
    is_wildcard: bool = False


@dataclass
class CallRef:
    """A function/method call reference."""

    caller_file: str
    caller_symbol: str
    callee_name: str
    line: int


@dataclass
class FileAnalysis:
    """Complete analysis of a single source file."""

    path: str
    language: Language
    lines_of_code: int
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    calls: list[CallRef] = field(default_factory=list)
    content_hash: str = ""


@dataclass
class RepoAnalysis:
    """Complete analysis of a repository."""

    root_path: str
    files: dict[str, FileAnalysis] = field(default_factory=dict)
    languages: dict[Language, int] = field(default_factory=dict)  # language -> file count
    total_loc: int = 0
    frameworks: list[str] = field(default_factory=list)
    build_systems: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)


@dataclass
class DependencyEdge:
    """A dependency relationship between files."""

    source: str
    target: str
    kind: str  # "imports", "calls", "extends"
    weight: int = 1  # number of references


@dataclass
class DependencyGraph:
    """File-level dependency graph."""

    edges: list[DependencyEdge] = field(default_factory=list)
    nodes: set[str] = field(default_factory=set)

    def add_edge(self, source: str, target: str, kind: str):
        """Add or increment a dependency edge."""
        for edge in self.edges:
            if edge.source == source and edge.target == target and edge.kind == kind:
                edge.weight += 1
                return
        self.edges.append(DependencyEdge(source=source, target=target, kind=kind))
        self.nodes.add(source)
        self.nodes.add(target)

    def get_dependents(self, file_path: str) -> list[str]:
        """Files that depend on the given file."""
        return [e.source for e in self.edges if e.target == file_path]

    def get_dependencies(self, file_path: str) -> list[str]:
        """Files that the given file depends on."""
        return [e.target for e in self.edges if e.source == file_path]
