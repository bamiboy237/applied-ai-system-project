from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codereview import llm
from codereview.patcher import CopilotResult
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_function_call_arguments_done_event import (
    ResponseFunctionCallArgumentsDoneEvent,
)
from openai.types.responses.response_output_item_added_event import (
    ResponseOutputItemAddedEvent,
)


class FakeStream:
    def __init__(self, events: list[SimpleNamespace], final_response: SimpleNamespace) -> None:
        self._events = events
        self._final_response = final_response

    def __enter__(self) -> FakeStream:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def __iter__(self):
        return iter(self._events)

    def get_final_response(self) -> SimpleNamespace:
        return self._final_response


class FakeResponsesAPI:
    def __init__(self, turns: list[tuple[list[SimpleNamespace], SimpleNamespace]]) -> None:
        self._turns = turns
        self.calls: list[dict[str, object]] = []

    def stream(self, **kwargs: object) -> FakeStream:
        self.calls.append(kwargs)
        events, final_response = self._turns.pop(0)
        return FakeStream(events, final_response)


class FakeClient:
    def __init__(self, turns: list[tuple[list[SimpleNamespace], SimpleNamespace]]) -> None:
        self.responses = FakeResponsesAPI(turns)


def make_response(
    *,
    response_id: str,
    output_text: str = "",
    output: list[object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(id=response_id, output_text=output_text, output=output or [])


def make_tool_call(*, name: str, arguments: str, call_id: str) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        name=name,
        arguments=arguments,
        call_id=call_id,
        type="function_call",
    )


def make_event(event_type: str, **kwargs: object) -> SimpleNamespace:
    if event_type == "response.output_item.added":
        return ResponseOutputItemAddedEvent(
            type="response.output_item.added",
            sequence_number=0,
            output_index=0,
            item=kwargs["item"],
        )
    if event_type == "response.function_call_arguments.done":
        return ResponseFunctionCallArgumentsDoneEvent(
            type="response.function_call_arguments.done",
            sequence_number=0,
            output_index=0,
            item_id="item_1",
            name=kwargs["name"],
            arguments=kwargs["arguments"],
        )
    return SimpleNamespace(type=event_type, **kwargs)


def test_review_context_returns_reviews_without_tool_calls(monkeypatch, capsys) -> None:
    fake_client = FakeClient(
        [
            (
                [
                    make_event("response.created", response=SimpleNamespace(id="resp_1")),
                    make_event("response.output_text.delta", delta="REVIEW:", item_id="msg_1", output_index=0, content_index=0),
                    make_event("response.completed"),
                ],
                make_response(response_id="resp_1", output_text="REVIEW:7: mutable default will leak state"),
            ),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda settings: fake_client)

    result = llm.review_context("## Target File\n7 | def process(items=[]):")

    assert result == CopilotResult(reviews={7: ["mutable default will leak state"]})
    assert len(fake_client.responses.calls) == 1
    stderr = capsys.readouterr().err
    assert "starting model turn 1" in stderr
    assert "model is drafting the review" in stderr
    assert "no tool calls requested; parsing final response" in stderr


def test_review_context_dispatches_tool_calls(monkeypatch, capsys) -> None:
    tool_call = make_tool_call(
        name="read_file",
        arguments='{"file_path":"codereview/prompts.py"}',
        call_id="call_1",
    )
    fake_client = FakeClient(
        [
            (
                [
                    make_event("response.created", response=SimpleNamespace(id="resp_1")),
                    make_event("response.output_item.added", item=tool_call),
                    make_event(
                        "response.function_call_arguments.done",
                        name="read_file",
                        arguments='{"file_path":"codereview/prompts.py"}',
                    ),
                    make_event("response.completed"),
                ],
                make_response(response_id="resp_1", output=[tool_call]),
            ),
            (
                [
                    make_event("response.created", response=SimpleNamespace(id="resp_2")),
                    make_event("response.output_text.delta", delta="REVIEW:", item_id="msg_1", output_index=0, content_index=0),
                    make_event("response.completed"),
                ],
                make_response(response_id="resp_2", output_text="REVIEW:3: prompt contract is too loose"),
            ),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda settings: fake_client)
    monkeypatch.setattr(
        llm.registry,
        "execute",
        lambda name, args: Path(
            "/Users/bogningguy-robert/Desktop/codereview/codereview/prompts.py"
        ).read_text(encoding="utf-8"),
    )

    result = llm.review_context("## Target File\n3 | prompt = get_system_prompt()")

    assert result == CopilotResult(reviews={3: ["prompt contract is too loose"]})
    assert len(fake_client.responses.calls) == 2
    assert fake_client.responses.calls[1]["previous_response_id"] == "resp_1"
    assert fake_client.responses.calls[1]["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": Path("/Users/bogningguy-robert/Desktop/codereview/codereview/prompts.py").read_text(encoding="utf-8"),
        }
    ]
    stderr = capsys.readouterr().err
    assert "model requested tool `read_file`" in stderr
    assert "running tool `read_file`" in stderr
    assert "tool `read_file` returned" in stderr


def test_review_context_returns_tool_error_as_follow_up_context(monkeypatch, capsys) -> None:
    tool_call = make_tool_call(
        name="read_file",
        arguments='{"file_path":"../outside.py"}',
        call_id="call_1",
    )
    fake_client = FakeClient(
        [
            (
                [
                    make_event("response.created", response=SimpleNamespace(id="resp_1")),
                    make_event("response.output_item.added", item=tool_call),
                    make_event(
                        "response.function_call_arguments.done",
                        name="read_file",
                        arguments='{"file_path":"../outside.py"}',
                    ),
                    make_event("response.completed"),
                ],
                make_response(response_id="resp_1", output=[tool_call]),
            ),
            (
                [
                    make_event("response.created", response=SimpleNamespace(id="resp_2")),
                    make_event("response.completed"),
                ],
                make_response(response_id="resp_2", output_text=""),
            ),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda settings: fake_client)

    result = llm.review_context("## Target File\n1 | pass")

    assert result == CopilotResult(reviews={})
    assert fake_client.responses.calls[1]["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "Error: '../outside.py' is outside the project root",
        }
    ]
    stderr = capsys.readouterr().err
    assert "Error running tool `read_file`" not in stderr
    assert "outside the project root" in stderr


def test_review_file_builds_context(monkeypatch, tmp_path, capsys) -> None:
    target = tmp_path / "sample.py"
    target.write_text("def greet(name):\n    return name\n", encoding="utf-8")
    monkeypatch.setattr(llm, "build_context", lambda path: f"context for {path.name}")
    monkeypatch.setattr(
        llm,
        "review_context",
        lambda context, message=llm.DEFAULT_TEACHER_MESSAGE: CopilotResult(
            reviews={2: [context, message]}
        ),
    )

    result = llm.review_file(target, message="Review only line 2")

    assert result == CopilotResult(
        reviews={2: ["context for sample.py", "Review only line 2"]}
    )
    assert f"assisting {target}" in capsys.readouterr().err


def test_review_context_parses_rewrite_response(monkeypatch) -> None:
    fake_client = FakeClient(
        [
            (
                [
                    make_event("response.created", response=SimpleNamespace(id="resp_1")),
                    make_event("response.completed"),
                ],
                make_response(
                    response_id="resp_1",
                    output_text="FILE_START\nprint('rewritten')\nFILE_END",
                ),
            ),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda settings: fake_client)

    result = llm.review_context("## Target File\n1 | print('old')")

    assert result == CopilotResult(reviews={}, rewritten_source="print('rewritten')")
