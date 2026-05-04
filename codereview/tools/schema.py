"""
Tool schema definitions.

Implements JSON Schema-compatible tool definitions:
- Parameter types and constraints
- Required vs optional parameters
- Enum values
- Nested object schemas

Schemas are used both for LLM context and argument validation.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator
from openai.types.responses.function_tool_param import FunctionToolParam


class ToolParameter(BaseModel):
    """Base class for tool Parameters."""

    name: str
    type: str
    description: str
    required: bool
    enum: list[str] | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate that the type is a supported JSON Schema primitive."""
        valid_types = {"string", "integer", "number", "boolean", "object", "array"}
        if v not in valid_types:
            raise ValueError(f"Invalid type: {v}")
        return v


class ToolSchema(BaseModel):
    """Schema definition for a tool."""

    name: str
    description: str
    parameters: list[ToolParameter]

    def to_json_schema(self) -> FunctionToolParam:
        """Convert ToolSchema to the Responses API function-tool format."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum is not None:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        parameters: dict[str, object] = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
            "strict": False,
        }
