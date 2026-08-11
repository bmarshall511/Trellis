# Git hooks

Versioned hooks, activated by pointing git at this directory:

```bash
git config core.hooksPath .githooks
```

Git will not do this automatically on clone — a repository that could install its own hooks on clone
would be a remote code execution vector. So it is one command, once per clone. Trellis warns at session
start if it has not been run.

- **pre-commit** — secret scan of staged changes, plus the Trellis integrity check. Sub-second.
- **pre-push** — every gate declared in `trellis.json`, cheapest first.

Both are dependency-free so they work before a stack is chosen.

`--no-verify` bypasses them. That is deliberate: a gate you cannot override becomes a gate people work
around in worse ways. But the agent is blocked from using it, and from setting `HUSKY=0`, `LEFTHOOK=0`
or any other bypass — see `.claude/hooks/guards/base.json`.
