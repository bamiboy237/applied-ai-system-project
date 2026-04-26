"""LLM wrapper and agentic loop for teacher-style comments or focused rewrites."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

from openai import OpenAI
from openai.types.responses.response import Response
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.function_tool_param import FunctionToolParam
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputItemParam, ResponseInputParam
from openai.types.responses.response_function_call_arguments_done_event import (
    ResponseFunctionCallArgumentsDoneEvent,
)
from openai.types.responses.response_output_item_added_event import ResponseOutputItemAddedEvent

from codereview.config import Settings, get_settings
from codereview.context import build_context
from codereview.patcher import CopilotResult, parse_copilot_result
from codereview.prompts import get_system_prompt
from codereview.tools import registry

MAX_TOOL_CALLS = 8
DEFAULT_TEACHER_MESSAGE = (
    "Review this file for correctness, broken behavior, and maintainability issues."
)
DEFAULT_REVIEW_MESSAGE = DEFAULT_TEACHER_MESSAGE


def _log(message: str) -> None:
    print(f"[codereview] {message}", file=sys.stderr, flush=True)


def get_client(settings: Settings) -> OpenAI:
    """Build the OpenAI client lazily so tests can patch it cleanly."""
    return OpenAI(api_key=settings.openai_api_key.get_secret_value())


def _build_initial_input(context: str, message: str) -> ResponseInputParam:
    """Wrap the user prompt and source context for the Responses API."""
    user_message: EasyInputMessageParam = {
        "role": "user",
        "content": (
            f"{message}\n\n"
            "Use tools only when the provided context is insufficient.\n\n"
            f"{context}"
        ),
    }
    return [
        user_message,
    ]


def _get_tools() -> list[FunctionToolParam]:
    """Return the tool definitions exposed to the model."""
    return registry.get_tools()


def _extract_function_calls(response: Response) -> list[ResponseFunctionToolCall]:
    """Filter a Responses API payload down to function-call items."""
    return [item for item in response.output if isinstance(item, ResponseFunctionToolCall)]


def _normalize_tool_output(result: object) -> str:
    """Convert any tool result into a string payload for the API."""
    return result if isinstance(result, str) else json.dumps(result, default=str)


def _summarize(text: str, limit: int = 120) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return single_line[: limit - 3] + "..."


def _dispatch_tool_call(tool_call: ResponseFunctionToolCall) -> ResponseInputItemParam:
    """Execute one model-requested tool call and package its output."""
    try:
        args = json.loads(tool_call.arguments)
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must decode to a JSON object")
        _log(f"running tool `{tool_call.name}` with args {_summarize(json.dumps(args, sort_keys=True))}")
        result = _normalize_tool_output(registry.execute(tool_call.name, args))
    except json.JSONDecodeError as exc:
        result = f"Error: invalid JSON arguments for tool '{tool_call.name}': {exc}"
        _log(_summarize(result))
    except Exception as exc:
        result = f"Error running tool '{tool_call.name}': {exc}"
        _log(_summarize(result))
    else:
        _log(f"tool `{tool_call.name}` returned {_summarize(result)}")

    output: FunctionCallOutput = {
        "type": "function_call_output",
        "call_id": tool_call.call_id,
        "output": result,
    }
    return output


def _stream_turn(
    *,
    client: OpenAI,
    turn_number: int,
    model: str,
    instructions: str,
    input_items: ResponseInputParam,
    tools: Iterable[FunctionToolParam],
    previous_response_id: str | None = None,
) -> Response:
    _log(f"starting model turn {turn_number}")
    saw_text = False
    with client.responses.stream(
        model=model,
        instructions=instructions,
        input=input_items,
        previous_response_id=previous_response_id,
        temperature=0.5,
        tools=tools,
        parallel_tool_calls=False,
    ) as stream:
        for event in stream:
            if getattr(event, "type", None) == "response.created":
                response = getattr(event, "response", None)
                if response is not None:
                    _log(f"response created: {response.id}")
            elif getattr(event, "type", None) == "response.in_progress":
                _log(f"model turn {turn_number} in progress")
            elif isinstance(event, ResponseOutputItemAddedEvent):
                item = event.item
                if isinstance(item, ResponseFunctionToolCall):
                    _log(f"model requested tool `{item.name}`")
            elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
                _log(
                    f"tool args ready for `{event.name}`: {_summarize(event.arguments)}"
                )
            elif getattr(event, "type", None) == "response.output_text.delta" and not saw_text:
                _log("model is drafting the review")
                saw_text = True
            elif getattr(event, "type", None) == "response.completed":
                _log(f"model turn {turn_number} completed")

        return stream.get_final_response()


def assist_context(context: str, message: str = DEFAULT_TEACHER_MESSAGE) -> CopilotResult:
    """Run the teacher loop for one request and return either comments or a rewrite."""
    settings = get_settings()
    client = get_client(settings)
    instructions = get_system_prompt()
    tools = _get_tools()
    response = _stream_turn(
        client=client,
        turn_number=1,
        model=settings.openai_model,
        instructions=instructions,
        input_items=_build_initial_input(context, message),
        tools=tools,
    )

    for turn_number in range(1, MAX_TOOL_CALLS + 1):
        tool_calls = _extract_function_calls(response)
        if not tool_calls:
            _log("no tool calls requested; parsing final response")
            return parse_copilot_result(response.output_text)

        tool_outputs = [_dispatch_tool_call(tool_call) for tool_call in tool_calls]
        response = _stream_turn(
            client=client,
            turn_number=turn_number + 1,
            model=settings.openai_model,
            instructions=instructions,
            input_items=tool_outputs,
            tools=tools,
            previous_response_id=response.id,
        )

    _log(f"reached max tool-call loop limit ({MAX_TOOL_CALLS}); parsing latest response")
    return parse_copilot_result(response.output_text)


def assist_file(target_file: Path, message: str = DEFAULT_TEACHER_MESSAGE) -> CopilotResult:
    """Build file context and return either teaching comments or a rewritten file."""
    _log(f"assisting {target_file}")
    return assist_context(build_context(target_file), message=message)


def review_context(context: str, message: str = DEFAULT_TEACHER_MESSAGE) -> CopilotResult:
    """Backward-compatible alias for the previous review-only API name."""
    return assist_context(context, message=message)


def review_file(target_file: Path, message: str = DEFAULT_TEACHER_MESSAGE) -> CopilotResult:
    """Backward-compatible alias for the previous review-only API name."""
    _log(f"assisting {target_file}")
    return review_context(build_context(target_file), message=message)
