# codereview

`codereview` is a CLI for teacher-style help on Python files. It can either inject strict `# REVIEW:` comments inline or make a small, focused rewrite when you explicitly ask for a change.

It works on one Python file at a time, builds local project context, lets the model call repo tools when needed, and then either comments on the file or prepares a full-file rewrite.

## Install

Set `OPENAI_API_KEY` in `.env` or your environment, then install globally with `uv`:

```bash
uv tool install --editable /path/to/codereview
```

That gives you a global `codereview` command.

## Usage

```bash
codereview --file <path> [--lines A-B] [--dry-run] [--clean] "<message>"
```

Examples:

```bash
codereview --file trial/buggy_service.py "review this file"
```

```bash
codereview --file trial/buggy_service.py "fix the SQLite path handling"
```

```bash
codereview --file trial/buggy_service.py --dry-run "review this file"
```

```bash
codereview --file trial/buggy_service.py --clean
```

## Behavior

- Vague requests like `"review this file"` stay in comment mode.
- Explicit, small change requests can trigger rewrite mode.
- Broad or ambiguous change requests should fall back to comments and guidance.
- `--dry-run` writes a unified diff to `/tmp/codereview_<file>_<hash>.diff`, opens it in `$EDITOR` or `zed`, and asks before applying.
- `--clean` removes previously injected `# REVIEW:` lines.

## Notes

- Python files only.
- `--clean` cannot be combined with `--dry-run` or an instruction.
- `--lines A-B` scopes comments or rewrites to a line range.
- Tool/activity progress is printed by default while the model is running.

## Trial Fixture

The `trial/` directory contains test targets:

- `trial/buggy_service.py`: large local-bug fixture
- `trial/force_tool_review.py`: cross-file fixture more likely to trigger tool use

Example:

```bash
codereview --file trial/force_tool_review.py "review this file and verify related helper behavior before commenting"
```
