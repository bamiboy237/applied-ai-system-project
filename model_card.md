# Model Card: BugHound + codereview

## Overview

BugHound + `codereview` is a Python-focused AI code-review system with two user surfaces. BugHound provides the starter-based Streamlit interface for snippet-level analysis, fix proposal, risk scoring, and trace visibility. The `codereview-ui` launcher opens that Streamlit app and includes a file-review tab that previews `codereview` diffs before writing.

`codereview` is the project I originally built from scratch. It uses an LLM as a strict senior-teacher assistant for one Python file at a time. It builds local context from the repo, can call a small set of repo tools, and returns either inline `# REVIEW:` comments or a focused rewrite when the request is explicit and narrow.

The point of the merged system is not to make the model look magical. It is to show how an AI code assistant can be constrained, tested, and kept inside a human review workflow.

## Intended Use

This system is meant to help a student or developer inspect Python code, identify reliability and maintainability issues, and preview small improvements. It is especially useful for:

- demonstrating an agentic plan, analyze, act, test, reflect workflow;
- comparing deterministic heuristics with OpenAI-generated analysis;
- adding senior-teacher-style comments to a real Python file;
- previewing local file comments, rewrites, and cleanup in a UI before applying them;
- practicing human-in-the-loop review before accepting AI-suggested changes.

## How It Works

BugHound takes a pasted Python snippet or sample snippet and runs:

1. Plan: log the scan and fix workflow.
2. Analyze: use local heuristics or OpenAI to detect issues.
3. Act: propose a heuristic or OpenAI-generated fix.
4. Test: score the proposed fix with deterministic risk rules.
5. Reflect: decide whether the change is safe enough to auto-apply or should require human review.

`codereview` takes a Python file path and an instruction, then:

1. validates the target file;
2. builds local context from project structure, direct imports, and the numbered target file;
3. runs an OpenAI teacher-agent prompt;
4. optionally dispatches constrained repo tools;
5. parses either `REVIEW:<line>:` comments or a full-file rewrite;
6. injects comments, writes a dry-run diff, applies a rewrite, or cleans old review comments.

The `File Review Chat` tab uses the same agentic loop, patching, and cleanup logic, but holds the result as a pending preview. It streams model-turn/tool-call progress while the agent runs, then shows the local file contents, unified diff, and collected trace before requiring the user to apply or discard the pending changes.

The file-review context has three layers:

- Project skeleton: Python files plus discovered functions and classes.
- Imported files: full source for local modules directly imported by the target.
- Target file: full source with line numbers so model comments can point to real lines.

## Inputs And Outputs

Inputs:

- short Python snippets in the BugHound UI;
- Python source files for the `codereview` CLI;
- optional line ranges for focused CLI review;
- user instructions such as "review this file" or "fix the SQLite path handling";
- local `.env` configuration containing `OPENAI_API_KEY` for OpenAI mode.

Outputs:

- detected issue objects;
- proposed fixed snippets;
- unified diffs;
- risk reports with score, level, reasons, and auto-fix decision;
- agent trace logs;
- inline `# REVIEW:` comments;
- dry-run diff files;
- focused full-file rewrites when the instruction clearly asks for a small change;
- pending UI previews that can be applied or discarded.

## Reliability And Safety Rules

The deterministic reliability layer matters because I do not think model output should be trusted by itself. Current guardrails include:

- Empty fix detection: if no fix is produced, risk is high and auto-fix is disabled.
- Severity scoring: high, medium, and low issue severities reduce the safety score.
- Large deletion check: fixes that become much shorter than the original are penalized.
- Return preservation check: removing all `return` statements from code that originally returned values is penalized.
- Bare-except modification check: changing broad exception handling is treated as useful but still review-worthy.
- Dry-run approval: `codereview --dry-run` shows a diff and asks before mutating the source file.
- UI confirmation: the `File Review Chat` tab validates a `.py` path, shows file contents and a generated diff, and requires an explicit apply action before comments, rewrites, or cleanup are written.
- Path sandboxing: repo tools validate paths against the configured project root.

These rules can create false positives. For example, a correct simplification may legitimately make a file much shorter. They can also create false negatives. For example, preserving a `return` statement does not prove the returned value is still correct.

## Limitations And Failure Modes

BugHound heuristics are intentionally simple. They catch obvious patterns such as `print`, `TODO`, and bare `except:`, but they miss deeper correctness problems, data-flow issues, security bugs, and cross-file behavior.

OpenAI analysis can be richer, but it can still hallucinate, overfit to visible context, miss a hidden dependency, or produce a fix that changes behavior. The risk assessor helps, but it is not a formal verifier.

`codereview` is limited by context quality. If the target file depends on behavior outside the provided context, the model may miss important issues. Tool use helps, but it is opportunistic: the model may decide not to call tools even when a human reviewer would.

The model also inherits prompt and context bias. If the initial context is too broad, irrelevant files can crowd out useful ones; if it is too narrow, the model may miss the exact dependency it needed to make a good judgment. The current system is especially sensitive to repo size, line-range selection, and whether the file depends on other files that are not directly included.

The UI accepts arbitrary local `.py` file paths. That is useful for demos and developer workflows, but it also means a user can point the system at sensitive source files. The current mitigation is narrow validation, visible preview, and explicit confirmation before any write. It does not prevent the user from sending selected file contents to OpenAI when file review is run with an API key configured.

Context size is also a practical limitation. Reading too many irrelevant files can bloat the prompt, increase cost, slow the run, and make the model less focused. The context builder excludes common dependency and generated folders such as `.venv`, `.git`, `__pycache__`, `node_modules`, `build`, and `dist`, but it still cannot know whether every project-local Python file is relevant or sensitive.

## Misuse Risk

The main misuse risk is treating model output as authoritative. This system should assist review, not replace review. A user could accept an incorrect rewrite, expose sensitive local files through over-broad context, or mistake a low risk score for proof of correctness.

The clearest file-review misuse risk is accidental exposure of irrelevant or sensitive files. During the original `codereview` work, one of the concrete concerns was that broad context scanning could pull in `.env` files, virtual-environment files, or cache artifacts. Those files do not help the model do its job, and they can bloat prompts, waste API calls, and potentially expose secrets.

That risk is also part of why I kept the tool intentionally bounded. I wanted the system to feel useful, but I did not want it to become a broad autonomous editor that changes code without a clear checkpoint.

Mitigations in this version:

- heuristic mode works offline and avoids API exposure;
- OpenAI mode is explicit and requires an API key;
- `codereview` targets one Python file at a time;
- the file-review UI accepts only existing `.py` files and previews the exact diff before mutation;
- automatic context construction and symbol search skip common dependency and generated folders;
- tools are narrow and path-checked;
- `--dry-run` keeps a human in the approval loop;
- `--clean` allows injected review comments to be removed predictably;
- tests cover deterministic behavior around parsing, patching, dry-run flow, and tool dispatch.

## Testing Summary

Current automated verification:

```text
53 passed
```

Covered areas:

- BugHound workflow shape;
- OpenAI/mock fallback behavior;
- risk scoring and auto-fix decisions;
- inline review parsing;
- patch injection and cleanup;
- dry-run diff behavior;
- context filtering for generated and dependency folders;
- live agent-loop trace collection for the Streamlit file-review tab;
- UI file validation and preview generation;
- consolidated prompt loading for the `codereview` teacher agent;
- `codereview-ui` launcher behavior;
- CLI validation;
- focused rewrite parsing;
- tool-call dispatch;
- tool-error handling.

The strongest-tested parts are deterministic: validation, parsing, patching, risk scoring, and fallback behavior. The least deterministic part is still model judgment itself, which is why I treat the model as one component inside a larger workflow rather than the whole system.

## Human-In-The-Loop Decision

The system should refuse or avoid auto-fix when:

- the fix removes major structure;
- the target contains broad exception handling, file deletion, database writes, network calls, authentication, or secrets;
- the model asks for a broad refactor instead of a focused change;
- the requested change affects code outside the visible context.

In those cases, the right behavior is to show a diff, explain risk, and require human approval.

## Reflection

The main lesson from this project is that useful AI systems are built around boundaries. The model is only one part of the system. The workflow around it matters just as much: context selection, output contracts, deterministic parsing, tests, local risk scoring, dry-run review, and cleanup.

The merged project also shows the difference between a demo agent and a practical developer tool. BugHound is good for explaining the reliability workflow visually. `codereview` is closer to an engineering workflow because it touches real files, uses repo context, and gives the user a patch they can inspect.

The next improvement would be a stronger context engine. That was one of the biggest lessons from the original `codereview` project: if the system sends too much irrelevant code to the model, the model becomes slower, more expensive, and less focused. A better version would retrieve the most relevant files without scanning too broadly, exclude generated and sensitive files by default, and make tool use more predictable.

## Collaboration With AI

For the original `codereview` project, I used AI tools in different roles rather than treating them as one replacement for engineering work. I used Perplexity AI for research and brainstorming around Python libraries like `difflib` and `ast`. I used Claude Code with Opus 4.6 to help turn that direction into a concise spec and to review parts of the file tools, AST behavior, and context-engine design. In the final cleanup phase, I used Codex with GPT-5.4 mini for refactors, tests, and static-checking issues.

One helpful AI suggestion was the dry-run diff workflow with human confirmation before mutating files. That improved safety and made the system easier to explain, demo, and trust.

The flawed side was the usual underengineering and overengineering that can show up when AI suggests structure without fully understanding the project. That is why I kept the final system small: one file at a time, a narrow tool set, deterministic patching, and explicit user approval before risky writes.

## Responsibility Reflection

This project is partly about building with AI without letting AI replace understanding. I used AI for research, review, cleanup, and implementation support, but the final work still needs to be something I can explain and maintain.

That matters because calling generated work my own without understanding it would not help me long term. It would not build a real skill, and it would make the codebase harder for me to reason about later. The responsible way for me to use these tools is as support for learning and execution, not as a substitute for actually knowing how the system works.
