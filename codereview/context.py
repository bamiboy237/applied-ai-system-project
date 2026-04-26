"""builds the context sent to the model - project skeleton, imported files, numbered target."""

import ast
from pathlib import Path

from codereview.config import get_settings

project_root = get_settings().project_root


def map_project_skeleton() -> list[str]:
    """Walk the project and return a list of formatted strings mapping each file to its defined functions and classes."""
    content = []
    for file in project_root.rglob("*.py"):
        try:
            file_tree = ast.parse(file.read_text())
        except (SyntaxError, OSError):
            continue
        definitions = [
            node.name
            for node in ast.walk(file_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        if definitions:
            content.append(
                f"### {file.relative_to(project_root)}\n{', '.join(definitions)}"
            )
    return content


def resolve_imports(target_file: Path) -> list[str]:
    """Parse imports from target_file and return the source contents of any that resolve to local project files."""
    module_map: dict[str, Path] = {}
    for file in project_root.rglob("*.py"):
        relative = file.relative_to(project_root)
        module_key = ".".join(relative.with_suffix("").parts)
        module_map[module_key] = file

    try:
        file_tree = ast.parse(target_file.read_text())
    except (SyntaxError, OSError):
        return []

    resolved: list[str] = []
    for node in ast.walk(file_tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module is None or node.level > 0:
                continue  # skip relative imports and bare `from . import x`
            modules = [node.module]
        else:
            continue

        for module in modules:
            if module in module_map:
                try:
                    resolved.append(module_map[module].read_text())
                except OSError:
                    pass

    return resolved


def build_context(target_file: Path) -> str:
    """Assemble the full context string to send to the model: skeleton → imports → numbered target."""
    sections: list[str] = []

    sections.append("## Project Skeleton\n" + "\n".join(map_project_skeleton()))

    imported = resolve_imports(target_file)
    if imported:
        joined = "\n\n---\n\n".join(imported)
        sections.append(f"## Imported Files\n{joined}")

    sections.append(
        f"## Target File: {target_file.name}\n{prepend_numberline(target_file)}"
    )

    return "\n\n".join(sections)


def prepend_numberline(target_file: Path) -> str:
    """Return the source of target_file with each line prefixed by its line number, e.g. '42 | def foo():'."""
    line_formatted_code_str = ""
    temporary_line_store = []
    for line_num, line_content in enumerate(
        target_file.read_text().splitlines(keepends=True), start=1
    ):
        temporary_line_store.append(f"{line_num} | {line_content}")
    line_formatted_code_str = "\n".join(temporary_line_store)
    return line_formatted_code_str
