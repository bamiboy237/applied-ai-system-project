"""tool registry and dispatcher — maps tool names to implementations and routes model tool calls."""

from typing import TYPE_CHECKING, Any, Callable

from .schema import ToolSchema

if TYPE_CHECKING:
    from codereview.tools.base import Tool


class ToolRegistry:
    tools: dict[str, Callable[..., str]]
    schemas: dict[str, ToolSchema]

    def __init__(self) -> None:
        self.tools = {}
        self.schemas = {}

    def register(self, schema: ToolSchema) -> Callable[[Callable[..., str]], Callable[..., str]]:
        """Decorator to register a function-based tool with its schema."""
        def decorator(func: Callable[..., str]) -> Callable[..., str]:
            self.tools[schema.name] = func
            self.schemas[schema.name] = schema
            return func
        return decorator

    def get_schema(self, name: str) -> ToolSchema | None:
        schema = self.schemas.get(name)
        if schema is None:
            raise KeyError(f'Schema "{name}" not found in registry')
        return schema

    def get_all_schemas(self) -> list[ToolSchema]:
        return list(self.schemas.values())

    def get_tools(self) -> list[dict[str, Any]]:
        """Return all tool schemas ready to pass to the Responses API."""
        return [schema.to_json_schema() for schema in self.get_all_schemas()]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        """Dispatch a tool call by name."""
        if name not in self.tools:
            raise ValueError(f'Tool "{name}" not found in registry')
        return self.tools[name](**args)


registry = ToolRegistry()


def register_tools(*tools: "Tool") -> None:
    """Register Tool instances into the global registry."""
    for tool in tools:
        registry.tools[tool.schema.name] = tool.execute
        registry.schemas[tool.schema.name] = tool.schema
