# Model Card: codereview

## Overview

`codereview` is a Python CLI that uses an LLM to review or lightly rewrite a single Python file at a time. It builds local context from the repo, can call a small set of repo tools, and returns either inline `# REVIEW:` comments or a focused rewrite when the request is explicit and narrow.

## Intended Use

This system is meant to help a developer inspect code, surface bugs and maintainability issues, and preview safe edits before applying them. It is designed as a constrained assistant, not an autonomous refactoring engine.

## Limitations And Biases

The biggest limitation of this system is that it is only as good as the context it sees. If the right code is not in context, the model can miss important issues that live outside the target file or outside the imported snippets it was given. On the other hand, if the context is too broad, it can get distracted by obvious local problems and miss the more important architectural issue.

The model also inherits prompt and context bias. If the initial context is too broad, irrelevant files can crowd out useful ones; if it is too narrow, the model may miss the exact dependency it needed to make a good judgment. The current system is especially sensitive to repo size, line-range selection, and whether the file depends on other files that are not directly included.

Another limitation is that tool use is opportunistic, not guaranteed. The model may decide it already has enough context and skip tools even when a human reviewer would probably want deeper inspection.

The other major issue we ran into was context performance. In its current form, changing or rebuilding context can be pretty slow, especially when the repository is larger or when irrelevant files are included. That makes the system more expensive to run and makes it clear that I need a stronger context engine that retrieves relevant code instead of scanning too much of the repository.

## Misuse Risk

The clearest misuse risk is accidental exposure of irrelevant or sensitive files. If the system is not properly guard-railed, it can be pointed at files that have nothing to do with the task, including local configuration files or other context files that should not be read by the model.

This showed up pretty clearly during testing. We had runs where the model was able to scan files that were not relevant to the task, including things like `.env` files, virtual-environment files, and `.pyc` caching artifacts. Those files do not help the model do its job, and they can seriously bloat the prompt, waste API calls, and potentially expose secrets.

To reduce that risk, the system needs stronger guardrails. It should only inspect files that are relevant to the task, keep the target to one file per run, support dry-run review before mutation, and explicitly exclude files and directories such as `.env`, `.venv`, `__pycache__`, and other generated artifacts from context construction.

## Reliability Observations

What surprised me most during testing was how often the deterministic parts of the system were stronger than the model behavior. The CLI validation, patching, and dry-run flow were stable, but the model's willingness to call tools depended heavily on prompt wording and how much context was already visible.

I also learned that context-window pressure is a real failure mode. When the system tried to include too much of a repo, the model stopped being useful before the code itself became more complex. That made it clear that building a robust context engine is not just an optimization detail; it is central to the reliability of the whole project.

Another thing I noticed was how dependent the system was on prompt engineering. I designed the tool to be fairly fluid while still being bounded by project guardrails, so the model could decide whether to leave comments or make a focused rewrite. But that flexibility meant the system was still heavily shaped by how specific the user instruction was. When the prompt was too generic or too broad, the model became less precise about what exact problem it was supposed to solve. This is not that different from other AI systems: if the instruction is broad, the model can struggle to pinpoint the real problem efficiently.

This is also why I want to explore other approaches. Right now the system works, but it leans a lot on prompt engineering and context assembly. I think the next real improvement is a stronger context engine that retrieves the right content without overwhelming the model.

## Collaboration With AI

I used a couple of different AI tools during this project, but each one played a different role. I started with Perplexity AI for research and brainstorming. I used it to learn more about Python's `difflib` library and the `ast` module, and that research influenced how I implemented the basic patching flow and the early context engine that passes Python structure to the model.

After a few iterations with Perplexity, I used Claude Code with the Opus 4.6 model at medium thinking to help me design a concise spec document. I then followed that spec while hand-coding most of the project myself. Claude Code was also useful when I wanted my code reviewed, especially around the file tools, the AST work, and the context-engine behavior. It helped point me toward cleaner implementations and better practices in those areas.

In the final phase of the project, I used Codex, specifically GPT-5.4 mini, to help me complete the last stretch of work, especially around refactors and dealing with static type-checker issues.

One helpful suggestion from AI was the dry-run diff workflow with human confirmation before mutating files. That improved safety and made the system easier to explain, demo, and trust.

One flawed suggestion was the usual AI under and overengineering of files.

## Responsibility Reflection

Like most projects, I did try to keep AI in the background as much as I could, and that is actually part of what inspired me to build this project in the first place. I noticed that when I started relying too much on tools like Claude Code to build things, I became less inclined to actually sit down and hand-write code. AI is useful because it helps me move fast, but there were also situations where I could not use those models, and I realized I was becoming less comfortable just writing code on my own.

For this project, I tried my best not to let AI do the real thinking for me. I mostly used it for research, review, and later-stage cleanup, while still making sure the final work was something I actually understood. At the end of the day, this is my project, and using AI to generate something that I call my own without understanding it would not really help me in the long run.

That would be a problem for me for two reasons. First, I would not actually learn anything valuable that could translate into a real skill or something meaningful on my resume. Second, if the project became too large, I would end up depending on those same AI tools just to understand my own codebase. With the cost of AI constantly going up, that is not a sustainable habit, especially as a college student.

So the broader lesson I take from this project is that AI is useful, but it should not replace understanding. The responsible way for me to use these tools is as support for learning and execution, not as a substitute for actually knowing how to build and reason about what I made.
