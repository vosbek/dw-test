"""Tree-sitter based AST parsing for multi-language code analysis.

Extracts symbols (classes, functions, methods), imports, and call relationships
from source files. This is our key advantage over DeepWiki-Open's naive text
splitting — we understand code structure and can ensure the RIGHT files get
into LLM context for each wiki page.
"""

import hashlib
import logging
from pathlib import Path

import tree_sitter_java as ts_java
import tree_sitter_javascript as ts_js
import tree_sitter_python as ts_python
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language as TSLanguage, Parser

from wiki_engine.ingestion.models import (
    CallRef,
    FileAnalysis,
    ImportRef,
    Language,
    LANGUAGE_EXTENSIONS,
    Symbol,
    SymbolKind,
)

logger = logging.getLogger(__name__)

# Tree-sitter language registry
_LANGUAGES: dict[Language, TSLanguage] = {}


def _init_languages():
    """Initialize tree-sitter language grammars."""
    global _LANGUAGES
    if _LANGUAGES:
        return
    _LANGUAGES = {
        Language.PYTHON: TSLanguage(ts_python.language()),
        Language.JAVA: TSLanguage(ts_java.language()),
        Language.JAVASCRIPT: TSLanguage(ts_js.language()),
        Language.TYPESCRIPT: TSLanguage(ts_typescript.language_typescript()),
    }


def detect_language(file_path: str) -> Language:
    """Detect programming language from file extension."""
    suffix = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(suffix, Language.UNKNOWN)


def parse_file(file_path: str, content: str | None = None) -> FileAnalysis:
    """Parse a source file and extract symbols, imports, and calls.

    Args:
        file_path: Path to the source file (relative to repo root).
        content: File content. If None, reads from disk.

    Returns:
        FileAnalysis with extracted symbols, imports, and call references.
    """
    _init_languages()

    if content is None:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")

    language = detect_language(file_path)
    lines_of_code = len([line for line in content.splitlines() if line.strip()])
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    analysis = FileAnalysis(
        path=file_path,
        language=language,
        lines_of_code=lines_of_code,
        content_hash=content_hash,
    )

    if language == Language.UNKNOWN or language not in _LANGUAGES:
        return analysis

    try:
        parser = Parser(_LANGUAGES[language])
        tree = parser.parse(content.encode())

        if language == Language.PYTHON:
            _extract_python(tree.root_node, content, analysis)
        elif language == Language.JAVA:
            _extract_java(tree.root_node, content, analysis)
        elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            _extract_js_ts(tree.root_node, content, analysis)
    except Exception:
        logger.warning("Failed to parse %s", file_path, exc_info=True)

    return analysis


def _node_text(node, source: str) -> str:
    """Extract text content of a tree-sitter node."""
    return source[node.start_byte:node.end_byte]


# -- Python Extraction --

def _extract_python(root, source: str, analysis: FileAnalysis):
    """Extract symbols and imports from Python AST."""
    for node in root.children:
        if node.type == "class_definition":
            _extract_python_class(node, source, analysis)
        elif node.type == "function_definition":
            _extract_python_function(node, source, analysis, parent=None)
        elif node.type in ("import_statement", "import_from_statement"):
            _extract_python_import(node, source, analysis)


def _extract_python_class(node, source: str, analysis: FileAnalysis):
    """Extract a Python class and its methods."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)

    # Build signature with bases
    sig = f"class {name}"
    superclasses = node.child_by_field_name("superclasses")
    if superclasses:
        sig += _node_text(superclasses, source)

    # Docstring
    docstring = _extract_python_docstring(node, source)

    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.CLASS,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
        docstring=docstring,
    ))

    # Extract methods
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "function_definition":
                _extract_python_function(child, source, analysis, parent=name)


def _extract_python_function(node, source: str, analysis: FileAnalysis, parent: str | None):
    """Extract a Python function or method."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)

    # Build signature
    params_node = node.child_by_field_name("parameters")
    params = _node_text(params_node, source) if params_node else "()"
    return_type = node.child_by_field_name("return_type")
    sig = f"def {name}{params}"
    if return_type:
        sig += f" -> {_node_text(return_type, source)}"

    docstring = _extract_python_docstring(node, source)

    kind = SymbolKind.METHOD if parent else SymbolKind.FUNCTION
    analysis.symbols.append(Symbol(
        name=name,
        kind=kind,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
        docstring=docstring,
        parent=parent,
    ))

    # Extract calls within the function body
    body = node.child_by_field_name("body")
    if body:
        _extract_calls(body, source, analysis, caller=f"{parent}.{name}" if parent else name)


def _extract_python_docstring(node, source: str) -> str:
    """Extract docstring from a Python class or function."""
    body = node.child_by_field_name("body")
    if not body or not body.children:
        return ""
    first = body.children[0]
    if first.type == "expression_statement":
        expr = first.children[0] if first.children else None
        if expr and expr.type == "string":
            text = _node_text(expr, source)
            return text.strip("\"'").strip()
    return ""


def _extract_python_import(node, source: str, analysis: FileAnalysis):
    """Extract Python import statements."""
    if node.type == "import_statement":
        for child in node.children:
            if child.type == "dotted_name":
                analysis.imports.append(ImportRef(
                    source_file=analysis.path,
                    imported_name=_node_text(child, source),
                    imported_from=_node_text(child, source),
                    line=node.start_point[0] + 1,
                ))
    elif node.type == "import_from_statement":
        module_node = node.child_by_field_name("module_name")
        module = _node_text(module_node, source) if module_node else ""
        for child in node.children:
            if child.type == "dotted_name" and child != module_node:
                analysis.imports.append(ImportRef(
                    source_file=analysis.path,
                    imported_name=_node_text(child, source),
                    imported_from=module,
                    line=node.start_point[0] + 1,
                ))
            elif child.type == "wildcard_import":
                analysis.imports.append(ImportRef(
                    source_file=analysis.path,
                    imported_name="*",
                    imported_from=module,
                    line=node.start_point[0] + 1,
                    is_wildcard=True,
                ))


# -- Java Extraction --

def _extract_java(root, source: str, analysis: FileAnalysis):
    """Extract symbols and imports from Java AST."""
    for node in root.children:
        if node.type == "class_declaration":
            _extract_java_class(node, source, analysis)
        elif node.type == "interface_declaration":
            _extract_java_interface(node, source, analysis)
        elif node.type == "import_declaration":
            _extract_java_import(node, source, analysis)
        elif node.type == "enum_declaration":
            _extract_java_enum(node, source, analysis)


def _extract_java_class(node, source: str, analysis: FileAnalysis):
    """Extract a Java class and its methods."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)

    # Build signature
    sig = f"class {name}"
    superclass = node.child_by_field_name("superclass")
    if superclass:
        sig += f" extends {_node_text(superclass, source)}"
    interfaces = node.child_by_field_name("interfaces")
    if interfaces:
        sig += f" implements {_node_text(interfaces, source)}"

    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.CLASS,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
    ))

    # Extract methods
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "method_declaration":
                _extract_java_method(child, source, analysis, parent=name)
            elif child.type == "constructor_declaration":
                _extract_java_method(child, source, analysis, parent=name)


def _extract_java_method(node, source: str, analysis: FileAnalysis, parent: str):
    """Extract a Java method."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)

    # Build signature
    type_node = node.child_by_field_name("type")
    return_type = _node_text(type_node, source) if type_node else ""
    params_node = node.child_by_field_name("parameters")
    params = _node_text(params_node, source) if params_node else "()"
    sig = f"{return_type} {name}{params}".strip()

    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.METHOD,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
        parent=parent,
    ))

    # Extract calls
    body = node.child_by_field_name("body")
    if body:
        _extract_calls(body, source, analysis, caller=f"{parent}.{name}")


def _extract_java_interface(node, source: str, analysis: FileAnalysis):
    """Extract a Java interface."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)
    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.INTERFACE,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=f"interface {name}",
    ))


def _extract_java_enum(node, source: str, analysis: FileAnalysis):
    """Extract a Java enum."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)
    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.ENUM,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=f"enum {name}",
    ))


def _extract_java_import(node, source: str, analysis: FileAnalysis):
    """Extract Java import statements."""
    text = _node_text(node, source).replace("import ", "").replace(";", "").strip()
    is_static = text.startswith("static ")
    if is_static:
        text = text.replace("static ", "")
    parts = text.rsplit(".", 1)
    module = parts[0] if len(parts) > 1 else ""
    name = parts[-1]
    analysis.imports.append(ImportRef(
        source_file=analysis.path,
        imported_name=name,
        imported_from=module,
        line=node.start_point[0] + 1,
        is_wildcard=name == "*",
    ))


# -- JavaScript/TypeScript Extraction --

def _extract_js_ts(root, source: str, analysis: FileAnalysis):
    """Extract symbols and imports from JS/TS AST."""
    for node in root.children:
        if node.type == "class_declaration":
            _extract_js_class(node, source, analysis)
        elif node.type in ("function_declaration", "export_statement"):
            if node.type == "export_statement":
                for child in node.children:
                    if child.type == "function_declaration":
                        _extract_js_function(child, source, analysis)
                    elif child.type == "class_declaration":
                        _extract_js_class(child, source, analysis)
            else:
                _extract_js_function(node, source, analysis)
        elif node.type == "import_statement":
            _extract_js_import(node, source, analysis)
        elif node.type == "lexical_declaration":
            _extract_js_const_function(node, source, analysis)


def _extract_js_class(node, source: str, analysis: FileAnalysis):
    """Extract a JS/TS class."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)
    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.CLASS,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=f"class {name}",
    ))
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "method_definition":
                m_name = child.child_by_field_name("name")
                if m_name:
                    analysis.symbols.append(Symbol(
                        name=_node_text(m_name, source),
                        kind=SymbolKind.METHOD,
                        file_path=analysis.path,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent=name,
                    ))


def _extract_js_function(node, source: str, analysis: FileAnalysis):
    """Extract a JS/TS function declaration."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)
    params = node.child_by_field_name("parameters")
    sig = f"function {name}{_node_text(params, source)}" if params else f"function {name}()"
    analysis.symbols.append(Symbol(
        name=name,
        kind=SymbolKind.FUNCTION,
        file_path=analysis.path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        signature=sig,
    ))


def _extract_js_const_function(node, source: str, analysis: FileAnalysis):
    """Extract arrow functions assigned to const/let/var."""
    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node and value_node and value_node.type == "arrow_function":
                name = _node_text(name_node, source)
                analysis.symbols.append(Symbol(
                    name=name,
                    kind=SymbolKind.FUNCTION,
                    file_path=analysis.path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=f"const {name} = (...) => ...",
                ))


def _extract_js_import(node, source: str, analysis: FileAnalysis):
    """Extract JS/TS import statements."""
    text = _node_text(node, source)
    # Extract the 'from' source
    source_node = node.child_by_field_name("source")
    if not source_node:
        return
    from_module = _node_text(source_node, source).strip("\"'")

    # Extract imported names
    for child in node.children:
        if child.type == "import_clause":
            for spec in _walk_tree(child):
                if spec.type == "identifier":
                    analysis.imports.append(ImportRef(
                        source_file=analysis.path,
                        imported_name=_node_text(spec, source),
                        imported_from=from_module,
                        line=node.start_point[0] + 1,
                    ))


# -- Shared Helpers --

def _extract_calls(node, source: str, analysis: FileAnalysis, caller: str):
    """Recursively extract function/method calls from a subtree."""
    for child in _walk_tree(node):
        if child.type == "call" or child.type == "method_invocation" or child.type == "call_expression":
            func_node = child.child_by_field_name("function") or child.child_by_field_name("name")
            if func_node:
                callee = _node_text(func_node, source)
                # Clean up method access chains to just the method name
                if "." in callee:
                    callee = callee.rsplit(".", 1)[-1]
                analysis.calls.append(CallRef(
                    caller_file=analysis.path,
                    caller_symbol=caller,
                    callee_name=callee,
                    line=child.start_point[0] + 1,
                ))


def _walk_tree(node):
    """Walk all descendant nodes."""
    cursor = node.walk()
    visited = False
    while True:
        if not visited:
            yield cursor.node
            if cursor.goto_first_child():
                continue
        if cursor.goto_next_sibling():
            visited = False
            continue
        if not cursor.goto_parent():
            break
        visited = True
