"""Repository scanner — clones repos and orchestrates file-level analysis.

Phase 0-1 of the pipeline: clone the repo, scan all files, parse ASTs,
build the file manifest and dependency graph.
"""

import logging
from pathlib import Path

from git import Repo

from wiki_engine.config import settings
from wiki_engine.ingestion.ast_parser import detect_language, parse_file
from wiki_engine.ingestion.models import (
    DependencyGraph,
    FileAnalysis,
    Language,
    RepoAnalysis,
)

logger = logging.getLogger(__name__)

# Files/dirs to always skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".gradle", "target", ".idea", ".vscode",
    ".settings", "bin", "obj", ".next", "out", ".cache",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "go.sum",
}

# Max file size to parse (500KB) — skip generated/minified files
MAX_FILE_SIZE = 500_000


def clone_repo(url: str, branch: str | None = None) -> Path:
    """Clone a repository to the configured clone directory.

    Returns the path to the cloned repo.
    """
    # Derive a directory name from the URL
    name = url.rstrip("/").split("/")[-1].replace(".git", "")
    owner = url.rstrip("/").split("/")[-2]
    clone_path = settings.git_clone_dir / f"{owner}__{name}"

    if clone_path.exists():
        logger.info("Repo already cloned at %s, pulling latest", clone_path)
        repo = Repo(clone_path)
        repo.remotes.origin.pull()
        return clone_path

    logger.info("Cloning %s to %s", url, clone_path)
    clone_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"depth": 1}
    if branch:
        kwargs["branch"] = branch
    Repo.clone_from(url, clone_path, **kwargs)
    return clone_path


def scan_repo(repo_path: Path) -> RepoAnalysis:
    """Scan a repository: detect languages, parse all source files.

    Returns a RepoAnalysis with file analyses, language stats, and metadata.
    """
    analysis = RepoAnalysis(root_path=str(repo_path))

    for file_path in _iter_source_files(repo_path):
        rel_path = str(file_path.relative_to(repo_path))
        language = detect_language(rel_path)

        if language == Language.UNKNOWN:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            logger.warning("Could not read %s", rel_path)
            continue

        file_analysis = parse_file(rel_path, content)
        analysis.files[rel_path] = file_analysis
        analysis.languages[language] = analysis.languages.get(language, 0) + 1
        analysis.total_loc += file_analysis.lines_of_code

    # Detect frameworks and build systems
    analysis.frameworks = _detect_frameworks(repo_path)
    analysis.build_systems = _detect_build_systems(repo_path)
    analysis.entry_points = _detect_entry_points(repo_path, analysis)

    logger.info(
        "Scanned %d files (%d LOC) in %s — languages: %s",
        len(analysis.files),
        analysis.total_loc,
        repo_path.name,
        {lang.value: count for lang, count in analysis.languages.items()},
    )
    return analysis


def build_dependency_graph(analysis: RepoAnalysis) -> DependencyGraph:
    """Build file-level dependency graph from import/call relationships."""
    graph = DependencyGraph()

    # Add all files as nodes
    for path in analysis.files:
        graph.nodes.add(path)

    # Map module names to file paths for import resolution
    module_to_file = _build_module_index(analysis)

    for path, file_analysis in analysis.files.items():
        # Resolve imports to file paths
        for imp in file_analysis.imports:
            target = _resolve_import(imp.imported_from, imp.imported_name, module_to_file)
            if target and target != path:
                graph.add_edge(path, target, "imports")

    return graph


def get_file_tree(repo_path: Path) -> str:
    """Generate a file tree string for the repository (for the wiki-architect prompt)."""
    lines = []
    _build_tree_lines(repo_path, repo_path, lines, prefix="")
    return "\n".join(lines[:500])  # Cap at 500 lines


def get_readme(repo_path: Path) -> str:
    """Read the README file if it exists."""
    for name in ("README.md", "README.rst", "README.txt", "README"):
        readme_path = repo_path / name
        if readme_path.exists():
            try:
                return readme_path.read_text(encoding="utf-8", errors="replace")[:10_000]
            except Exception:
                pass
    return ""


# -- Private Helpers --

def _iter_source_files(repo_path: Path):
    """Iterate over source files, skipping irrelevant dirs and files."""
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.stat().st_size > MAX_FILE_SIZE:
            continue
        if detect_language(str(path)) != Language.UNKNOWN:
            yield path


def _detect_frameworks(repo_path: Path) -> list[str]:
    """Detect frameworks by looking for telltale config files."""
    frameworks = []
    markers = {
        "Spring Boot": ["pom.xml", "build.gradle"],
        "Django": ["manage.py", "django"],
        "Flask": ["flask"],
        "FastAPI": ["fastapi"],
        "React": ["package.json"],
        "Angular": ["angular.json"],
        "Express": ["express"],
        ".NET": ["*.csproj", "*.sln"],
    }
    for framework, files in markers.items():
        for pattern in files:
            if any(repo_path.glob(f"**/{pattern}")):
                frameworks.append(framework)
                break
    return frameworks


def _detect_build_systems(repo_path: Path) -> list[str]:
    """Detect build systems."""
    systems = []
    markers = {
        "Maven": "pom.xml",
        "Gradle": "build.gradle",
        "npm": "package.json",
        "pip": "requirements.txt",
        "Poetry": "pyproject.toml",
        "MSBuild": "*.csproj",
        "Make": "Makefile",
    }
    for system, marker in markers.items():
        if any(repo_path.glob(marker)):
            systems.append(system)
    return systems


def _detect_entry_points(repo_path: Path, analysis: RepoAnalysis) -> list[str]:
    """Detect likely entry points."""
    entry_points = []
    candidates = [
        "main.py", "app.py", "server.py", "index.js", "index.ts",
        "Main.java", "Application.java", "Program.cs", "Startup.cs",
    ]
    for name in candidates:
        matches = list(repo_path.glob(f"**/{name}"))
        for match in matches:
            entry_points.append(str(match.relative_to(repo_path)))
    return entry_points


def _build_module_index(analysis: RepoAnalysis) -> dict[str, str]:
    """Map module/package names to file paths for import resolution."""
    index: dict[str, str] = {}
    for path in analysis.files:
        # Python: convert path to module notation
        if path.endswith(".py"):
            module = path.replace("/", ".").replace("\\", ".").removesuffix(".py")
            if module.endswith(".__init__"):
                module = module.removesuffix(".__init__")
            index[module] = path
        # Java: use the file name as class name
        elif path.endswith(".java"):
            class_name = Path(path).stem
            index[class_name] = path
        # JS/TS: use relative path patterns
        elif any(path.endswith(ext) for ext in (".js", ".ts", ".jsx", ".tsx")):
            stem = Path(path).stem
            if stem == "index":
                parent = str(Path(path).parent)
                index[parent] = path
            index[stem] = path
            index[path] = path
    return index


def _resolve_import(
    from_module: str, name: str, module_to_file: dict[str, str]
) -> str | None:
    """Try to resolve an import to a file path in the repo."""
    # Try the full module path
    if from_module in module_to_file:
        return module_to_file[from_module]
    # Try the imported name itself
    if name in module_to_file:
        return module_to_file[name]
    # Try submodule (e.g., "com.example.service" -> "service")
    parts = from_module.split(".")
    for i in range(len(parts)):
        sub = ".".join(parts[i:])
        if sub in module_to_file:
            return module_to_file[sub]
    return None


def _build_tree_lines(
    base: Path, current: Path, lines: list[str], prefix: str, max_depth: int = 4
):
    """Recursively build file tree lines."""
    if len(lines) > 500:
        return
    depth = len(current.relative_to(base).parts)
    if depth > max_depth:
        return

    entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    for i, entry in enumerate(entries):
        if entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            _build_tree_lines(base, entry, lines, prefix + extension, max_depth)
