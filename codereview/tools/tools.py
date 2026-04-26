"""tools the model can call to pull more context - read files, grab functions, find symbols."""

import ast
from pathlib import Path
from typing import ClassVar, override

from codereview.config import get_settings
from codereview.tools.base import Tool
from codereview.tools.registry import register_tools
from codereview.tools.schema import ToolParameter, ToolSchema


def _validate_path(file_path: str) -> tuple[bool, Path | None, str | None]:
    """Resolve and sandbox a path to the project root. Returns (ok, path, error)."""
    root = get_settings().project_root
    resolved = (root / file_path).resolve()
    if not resolved.is_relative_to(root):
        return False, None, f"'{file_path}' is outside the project root"
    return True, resolved, None


class ReadFileTool(Tool):
    schema: ClassVar[ToolSchema] = ToolSchema(
        name="read_file",
        description="Read the full contents of a file in the project.",
        parameters=[
            ToolParameter(name="file_path", type="string", description="Path to the file, relative to the project root.", required=True),
        ],
    )

    @override
    def execute(self, **kwargs: object) -> str:
        file_path = str(kwargs.get("file_path", ""))
        raw_max = kwargs.get("max_chars")
        max_chars = int(raw_max) if isinstance(raw_max, int) else None
        ok, path, err = _validate_path(file_path)
        if not ok or path is None:
            return f"Error: {err}"
        try:
            contents = path.read_text(encoding="utf-8")
            if max_chars and len(contents) > max_chars:
                contents = contents[:max_chars] + f"\n\n... truncated at {max_chars} characters"
            return contents
        except OSError as e:
            return f"Error reading '{file_path}': {e}"


class GetFunctionTool(Tool):
    schema: ClassVar[ToolSchema] = ToolSchema(
        name="get_function",
        description="Extract the source of a named function or class from a file.",
        parameters=[
            ToolParameter(name="file_path", type="string", description="Path to the file, relative to the project root.", required=True),
            ToolParameter(name="name", type="string", description="Name of the function or class to extract.", required=True),
        ],
    )

    @override
    def execute(self, **kwargs: object) -> str:
        file_path = str(kwargs.get("file_path", ""))
        name = str(kwargs.get("name", ""))
        ok, path, err = _validate_path(file_path)
        if not ok or path is None:
            return f"Error: {err}"
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as e:
            return f"Error parsing '{file_path}': {e}"
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                return ast.get_source_segment(source, node) or f"Could not extract source for '{name}'"
        return f"'{name}' not found in {file_path}"


class SearchSymbolTool(Tool):
    schema: ClassVar[ToolSchema] = ToolSchema(
        name="search_symbol",
        description="Find where a symbol is defined and called across the whole project.",
        parameters=[
            ToolParameter(name="symbol", type="string", description="Function or class name to search for.", required=True),
        ],
    )

    @override
    def execute(self, **kwargs: object) -> str:
        symbol = str(kwargs.get("symbol", ""))
        root = get_settings().project_root
        results: list[str] = []
        for py_file in root.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError):
                continue
            rel = py_file.relative_to(root)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
                    results.append(f"DEFINED  {rel}:{node.lineno}")
                elif isinstance(node, ast.Call):
                    func = node.func
                    call_name = (
                        func.id if isinstance(func, ast.Name)
                        else func.attr if isinstance(func, ast.Attribute)
                        else None
                    )
                    if call_name == symbol:
                        results.append(f"CALLED   {rel}:{node.lineno}")
        return "\n".join(results) if results else f"'{symbol}' not found in project"


register_tools(ReadFileTool(), GetFunctionTool(), SearchSymbolTool())
