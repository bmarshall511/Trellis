# setup/

Files that belong at the repo root but would be broken sitting in an empty repo — a test runner config
pointing at a dev server that does not exist, a linter importing a plugin that is not installed.

They are copied to the root when a project's stack is chosen.

- **trellis.json** — the project declaration. Always copied first, before anything else, because
  everything in Trellis reads it. Validate it with `.claude/scripts/validate-config.py`.

Stack modules contribute their own files here via `stacks/<name>/setup/`.
