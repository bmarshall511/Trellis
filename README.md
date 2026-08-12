# Trellis

**A structure that guides how AI agents build software** — so the result is clean, tested, accessible,
secure and maintainable, regardless of what it's built with.

Trellis contains no application and no stack. It is the process, the standards and the guardrails.

---

## The problem

Coding agents are capable and inconsistent. The same agent, given the same task on two different days,
produces work of very different quality — because nothing holds it to a standard between sessions.

So you re-explain yourself. Every new project, you set up the same conventions, restate the same
expectations, and rediscover the same mistakes. Then a session ends, the context is gone, and the next
one starts from nothing.

Trellis is the part you'd otherwise rebuild every time.

## What it actually does

**Nothing gets built from a guess.**
Specs are written interactively — the agent interrogates you until nothing is ambiguous, and a readiness
checklist refuses a spec containing words like "appropriate" or "handle", because each one hides a
decision that would otherwise be invented at 3am. Implementation then runs without questions. It finishes
green, or it stops and writes down the single thing it couldn't resolve. It never assumes.

**Nothing merges without proof.**
Every acceptance criterion must map to a test that would fail if that criterion broke. Not a coverage
percentage — coverage measures which lines ran, not which promises hold. A hook prevents the agent from
ending its turn while any gate is red, so "Claude says it's done" becomes "Claude proved it's done".

**Production cannot be damaged.**
Enforced by what exists rather than by what the agent was told. A guard blocks 31 dangerous command
shapes and catches the evasions — environment-variable prefixes, pipes, base64. It is the third line of
defence and the weakest; the first is that production write credentials never exist on the machine.

**Work can run unattended, and cannot lie about it.**
A run implements one spec on its own branch with no human present, and ends in exactly one of four
states: done, blocked, failed, or tampered. The verdict comes from the gates and the coverage — never
from what the agent says. It cannot publish, merge, install dependencies, or edit its own guardrails,
and if the guardrail files change during a run, every other result from that run is discarded.

**Context survives the session.**
A handoff is written before compaction, with a copy-pastable prompt. A generated map means an agent reads
an overview instead of the whole codebase.

**Designs are approved before they're built.**
Approval is bound to a hash of the mockup *and* the design tokens it was rendered against, so editing
either one voids it automatically. A file-existence check would have been forgeable.

## What it is not

- Not a framework, boilerplate or starter app. There is no application here
- Not tied to a language, framework, database or host
- Not a set of suggestions. The gates fail builds

## How it works

Three layers.

**The core** is stack-agnostic and always active: ten skills written as principles, three read-only
reviewer agents, nine commands, four hooks. It knows nothing about any specific technology.

**Stack modules** hold what's known about specific technologies — version traps, quota cliffs, correct
patterns, deprecations, and the dangerous commands that tooling makes possible. A module loads **only**
if a project declares it, so you pay no context for technologies you don't use. Each carries a dated
`VERIFIED` file, because technology knowledge decays fast.

**The project declaration** (`trellis.json`) says what a project is and what it's built with. Everything
reads it. Trellis defines *what* must be verified; stack modules decide *how*:

| Gate | Must |
|---|---|
| `types` | Fail on any type error |
| `lint` | Fail on any lint error |
| `test` | Run the full suite, fail on any failure |
| `a11y` | *(UI only)* Fail on any accessibility violation |
| `perf` | *(UI only)* Fail on any performance budget breach |

A gate that doesn't apply is *declared* absent. It is never silently missing — absence is a decision.

Project type decides which parts of the process are active:

| | Specs | Tests | Mockups | Accessibility |
|---|---|---|---|---|
| `app` — has a user interface | ✓ | ✓ | ✓ | ✓ |
| `service` — API, no interface | ✓ | ✓ | — | — |
| `cli` | ✓ | ✓ | — | — |
| `library` | ✓ | ✓ | — | — |

## Getting started

```bash
git clone https://github.com/bmarshall511/Trellis.git my-project
cd my-project
rm -rf .git && git init
git config core.hooksPath .githooks
```

That last line matters. Git won't activate a repository's own hooks on clone — a repo that could would be
a remote code execution vector — so it's one command, once. Trellis warns you at session start if you
forget.

Then open Claude and say what you want to build:

```
claude
> I want to build a tool that tracks my reading list
```

The agent interviews you, recommends a stack for *those* requirements, and writes `trellis.json`. It
won't scaffold anything before you've agreed to the choices.

### Commands

| | |
|---|---|
| `/spec-new` | Write a spec. Interviews you until nothing is ambiguous |
| `/spec-next` | Build the next ready spec |
| `/spec-status` | Every spec's real status, computed from disk rather than trusted |
| `/spec-verify` | Prove a spec is done — every criterion tested, every gate green |
| `/mockup` | Design a screen, or the project's visual foundations, for approval |
| `/audit` | Audit against the standards. Changes nothing |
| `/map` | Regenerate the project map |
| `/handoff` | Write a handoff for a fresh session |
| `/stack-add` | Research a technology and add it as a stack module |
| `/run` | Run ready specs unattended, halting on the first blocker |

### Layout

```
.claude/skills/     standards and process, written as principles
.claude/commands/   the commands above
.claude/agents/     read-only reviewers and auditors
.claude/hooks/      guardrails that run automatically
.claude/scripts/    map, mockup approval, secret scanning, integrity checks
.githooks/          secret scanning on commit, gates on push
stacks/             technology knowledge, loaded only when used
docs/specs/         your specs
docs/mockups/       approved designs, kept for reference
docs/map/           generated overview so agents don't re-read the codebase
setup/              config staged until a stack is chosen
trellis.json        what this project is and what it's built with
```

## Adding a technology

`stacks/` ships two worked modules — Supabase and GitHub — plus a template. `/stack-add <name>` researches a technology
against primary sources and writes the module.

A module can contribute a skill, guard patterns, a map extractor and staged config. See
[stacks/README.md](stacks/README.md).

**Every guard pattern needs a test.** An untested guard is not a guard — the first version of the
production guard in this repo allowed everything through, and only a test caught it.

## Verifying it

```bash
.claude/hooks/tests/run.py                   # 51 production-guard cases
.claude/scripts/tests/run-secret-tests.py    # 22 secret-scanner cases
.claude/scripts/check-integrity.py           # cross-references resolve
.claude/scripts/spec-lint.py                 # specs meet the readiness checklist
.claude/scripts/spec-coverage.py             # every criterion has a test
.claude/scripts/build-map.py --check         # map is current
.claude/scripts/tests/run-loop-tests.sh      # 6 unattended-run scenarios
stacks/github/tests/run-risk-tests.py        # 32 risk-classification cases
```

The integrity check exists because each piece can be individually correct while the whole is broken — a
command loading a renamed skill is silently a no-op, and nothing about it looks wrong.

## Status

Early, but no longer untested. Trellis has been used to build a real (small) tool end to end — spec
interview, twelve acceptance criteria, implementation, gates, commit. That run found eight defects in
Trellis itself, all since fixed. The most useful thing it proved: the verify gate genuinely refused to
let the work be called done while lint was failing.

It has since also been used to build something with a user interface — three design directions merged
into approved foundations, a mockup with every state, and the accessibility and performance gates that
`type: app` requires. That run found four more defects, including a secret scanner that flagged 117 npm
integrity hashes and would have blocked the first commit of any Node project.

The unattended runner is tested against six scenarios, three of them adversarial: an agent that claims
success with a gate red, one that claims success with a criterion untested, and one that disables the
gates and then claims success. All three are caught. The GitHub module's risk classifier — which decides
what may merge without review — is tested against 32 cases, including that an additive migration is
auto-mergeable while the same file containing `drop column` is not.

What still hasn't happened is a real overnight run against a real model, or use at any scale.

Stack modules are the natural contribution: self-contained, they don't touch the core, and their value is
entirely in being current.

## Licence

MIT
