# Trial Files

This directory now has two kinds of fixtures:

## `buggy_service.py`
Large monolith with many obvious local problems.
This is good for testing comment injection, but it may not trigger tool calls because
the target file plus direct imports already give the model enough to review.

## `force_tool_review.py`
Smaller cross-file fixture designed to make tool use more likely.

How it is structured:
- `force_tool_review.py` is the target
- `gateway.py` is a direct import, so it is likely to appear in the initial context
- `hidden_rules.py` contains the important second-hop behavior that is not directly included
- `batch_jobs.py` provides external callers so `search_symbol` can become useful

Suggested commands:

```bash
# Standard fixture with lots of local bugs
codereview --file trial/buggy_service.py "review this file"
```

```bash
# Cross-file fixture meant to encourage tool calls
codereview --file trial/force_tool_review.py "review this file and verify related helper behavior before commenting"
```

```bash
# Dry run the cross-file fixture
codereview --file trial/force_tool_review.py --dry-run "review this file and verify related helper behavior before commenting"
```

```bash
# Clean injected comments after testing
codereview --file trial/force_tool_review.py --clean
```
