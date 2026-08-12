# Session handoff

Written on request at 2026-08-12 00:12 UTC.

---

## What I was doing

**Goal:** build Trellis — a repo you download that guides how AI agents build software. It contains no
application and no stack; it is process, standards and guardrails. Public at
https://github.com/bmarshall511/Trellis

**Finished and verified.** Eight commits, all pushed. Five test suites pass:

| Suite | Covers |
|---|---|
| `.claude/hooks/tests/run.py` | 61 production-guard cases |
| `.claude/scripts/tests/run-secret-tests.py` | 26 secret-scanner cases |
| `.claude/scripts/tests/run-loop-tests.sh` | 6 unattended-run scenarios, 3 adversarial |
| `stacks/github/tests/run-risk-tests.py` | 32 risk-classification cases |
| `.claude/scripts/check-integrity.py` | cross-references resolve |

Contents: 10 skills, 3 agents, 10 commands, 4 hooks, 8 scripts, 2 stack modules (supabase, github).

**Proven by use.** Trellis was used to build two throwaway projects — a CLI (`dupefind`) and a UI app
(a contrast checker). Those runs found **twelve defects in Trellis**, all fixed. The most valuable:

- The secret scanner flagged 117 npm integrity hashes, which would have blocked the first commit of any
  Node project while Trellis's own security skill says to commit the lockfile.
- The coverage mapper followed paths inside gate scripts and picked up `src/` files, meaning a **comment
  in source code could satisfy the coverage gate**.
- The first production guard allowed everything — a heredoc meant Python read the script from stdin
  instead of the command. Only a test caught it.

**What did NOT work, so it is not retried:**

- `ruff --fix` reformatted nine files to f-strings mid-session. Later string-replacement edits written
  against the old `%`-format text silently failed to match. If an edit appears not to apply, check
  whether the file was reformatted; use line-wise edits.
- `set -e` plus `pipefail` killed `run-spec.sh`'s report writer, because `spec-coverage.py` exits
  non-zero exactly when there is something to report. `finish()` now runs under `set +e`.
- ES modules do not load over `file://`. A UI gate will pass against a blank page. Gates need a server.
- An a11y checker needs `browser.newContext()`, not `browser.newPage()`.

**Decisions made in conversation and now recorded in the repo:** Trellis is one downloadable repo, no
CLI, no app scaffold. Stack is a strong recommendation, not a fixture. `PLAN.md` and `DECISIONS.md` are
deliberately gitignored — they were notes about building Trellis, not part of it.

**Verified this session:** CLI is 2.1.227; `--permission-mode dontAsk`, `--setting-sources` and
`--settings` all exist, so the unattended runner's launch command is valid.

## Not proven — read before trusting

1. **No real overnight run.** The loop is tested against a mock agent only.
2. **The three reviewer agents have never been invoked.**
3. **Skill triggering is untested** — whether skills load when relevant is unknown.
4. **Five commands never run:** `/audit`, `/handoff` (running now), `/stack-add`, `/spec-status`,
   `/spec-verify`.
5. **Only two stack modules.** A Next.js project gets the core and nothing Next-specific.
6. **GitHub half unverified against a live repo.** Without required status checks, `gh pr merge --auto`
   has nothing to wait on and that gate is decorative.
7. **The author was also the tester.** Both test builds were done by someone who already knew the design
   intent, so it is unknown whether the *written* skills are sufficient. A fresh session following only
   what is written is a genuinely different test.

## Next step

Start a real application with Trellis, using the interactive path only — that path is proven; the
unattended loop is not. Leave `autonomy.enabled: false` until several specs have been built while
watching.

Run `/stack-add <name>` for each technology as it is actually needed, rather than building modules
speculatively that go stale before use.

Expect the first real project to find defects. The last two found twelve between them, and each round
has been cheaper than the one before.

---

## State at handoff

**Branch:** `main`

**Uncommitted files (2):**

- `claude/hooks/write-handoff.py`
- `docs/handoff/`

**Recent commits:**

```
b3ab307 GitHub stack module: publish, classify, gate
e5f2440 Unattended run loop
47a3063 Fix four defects found by building something with a UI
49846a8 Fix eight defects found by using Trellis to build something
d9fccfa Enforce map freshness in pre-commit
904f4fa Rewrite README as the project's front door; add licence
8e6da80 Baseline configuration active on download
9eaa753 Trellis core: process, standards and guardrails
```

---

## Paste this into a new session

```
Continuing work on Trellis.

Read docs/handoff/LATEST.md first — it has the full state of where I left off.

Branch: main

Do not start anything new until you have confirmed with me what state the
in-flight work is actually in.
```
