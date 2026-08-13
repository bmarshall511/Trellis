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
Enforced by what exists rather than by what the agent was told. A guard catches destructive commands
and the ways they get disguised — environment-variable prefixes, pipes, base64, command substitution
inside an argument that looks like prose. Stack modules add their own patterns, loaded only when that
stack is in use.

It is the third line of defence and the weakest, and the file says so: a denylist can never be
complete. The first line is that production write credentials never exist on the machine; the second
is that the production role has no write grants.

**Work runs unattended, end to end, and cannot lie about it.**
A run takes one spec and does the whole job with nobody present: branch, implement, commit, push, open
a pull request, wait for CI, fix whatever CI finds, merge, and move to the next spec. It ends in one of
four states — done, blocked, failed, or tampered — and the verdict comes from the gates and the coverage
mapper, never from what the agent says about itself. If the guardrail files change during a run, every
other result from that run is discarded.

What it may not do is narrow and deliberate: no force pushes, no history rewrites, no new dependencies,
no editing its own gates or CI config. Merging is not on that list, because merging is not the dangerous
step — merging something that has not passed the gates and the risk classifier is, and both run before
the pull request is even opened.

**Context survives the session.**
A handoff is written before compaction, with a copy-pastable prompt. A generated map means an agent reads
an overview instead of the whole codebase.

**Designs are approved before they're built.**
Approval is bound to a hash of the mockup *and* everything it was rendered against — tokens, brand
assets, fonts — so changing any of it voids the approval automatically. A file-existence check would
have been forgeable.

## What it is not

- Not a framework, boilerplate or starter app. There is no application here
- Not tied to a language, framework, database or host
- Not a set of suggestions. The gates fail builds

## How it works

Three layers.

**The core** is stack-agnostic and always active: ten skills written as principles, three read-only
reviewer agents, eleven commands, four hooks. It knows nothing about any specific technology.

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
git config merge.trellis-generated.name 'regenerate Trellis-generated files'
git config merge.trellis-generated.driver '.claude/scripts/merge-generated.sh %A %O %B %P'
```

Those last three matter, and git will not do any of them for you on clone — a repository that could
activate its own hooks would be a remote code execution vector. So they are one-time, per clone, and
Trellis warns you at session start if either is missing.

The merge driver handles files Trellis generates. Without it, two branches that both regenerate the
project map merge *cleanly* and produce a map that is quietly wrong — worse than a conflict, because a
conflict announces itself.

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
| `/spec-next` | Build the next ready spec — same branch, report and delivery as an unattended run |
| `/deliver` | Deliver finished work: PR, CI, merge, through the sanctioned path |
| `/spec-status` | Every spec's real status, computed from disk rather than trusted |
| `/spec-verify` | Prove a spec is done — every criterion tested, every gate green |
| `/mockup` | Design a screen, or the project's visual foundations, for approval |
| `/audit` | Audit against the standards. Changes nothing |
| `/map` | Regenerate the project map |
| `/handoff` | Write a handoff for a fresh session |
| `/stack-add` | Research a technology and add it as a stack module |
| `/run` | Run ready specs unattended, halting on the first blocker |

### Running unattended

Off by default. Turn it on in `trellis.json`:

```json
"autonomy": {
  "enabled": true,
  "mayMerge": true,
  "mergeVia": "pull-request",
  "maxRepairAttempts": 2,
  "onBlocked": "halt"
}
```

Then `.claude/scripts/run-queue.sh` works through every ready spec, delivering each before starting
the next.

| `mergeVia` | What happens |
|---|---|
| `local` | Merges on this machine, never contacts the host. Nothing is pushed. |
| `pull-request` | Pushes the branch, opens a PR, polls CI, fixes what CI finds, merges when green, and fast-forwards local `main` so the next spec builds on it. |

Both go through a single audited script that re-runs the gates on the branch, checks every acceptance
criterion is covered, and asks the risk classifier first.

**Interactive and unattended produce the same artifacts** — the `agent/<spec-id>` branch and the run
report — so work built with `/spec-next` delivers through exactly the same path. They differ only in
whether questions may be asked, never in what they leave behind. Opening a pull request by hand skips
every check above and produces one nothing will merge automatically, because the branch and report the
delivery script looks for were never made.

**A run halts the queue rather than pressing on** when a spec blocks, when CI stays red past
`maxRepairAttempts`, or when the risk classifier says a change needs a human. One thing to decide in
the morning beats a pile of half-built branches — and if spec 3 turned out to be ambiguous, specs 4
and 5 written the same evening probably are too.

**What the classifier holds back** is in `stacks/github/risk-policy.json`: auth, migrations that drop
or truncate, dependencies, CI config, payments, infrastructure, and public-facing content. Read it
once and adjust it. Too strict and you wake to held branches; too loose and the gate is decorative.

**Before the first overnight run**, check that your repository has required status checks on its
default branch. Without them CI can pass and the merge still be refused, which the script reports but
cannot fix. And run one spec while you are awake — the loop's job is to reproduce something you
already trust.

### Updating

```bash
.claude/scripts/trellis-update.sh --check   # what would change
.claude/scripts/trellis-update.sh           # apply it
```

Framework files are replaced wholesale; your own files are never touched, and `trellis.json` keeps its
contents. It reads the file set from the *upstream* manifest rather than a list written down here,
because a list written down here would be wrong within a month.

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
.claude/hooks/tests/run.py                   # 102 production-guard cases
.claude/scripts/tests/run-secret-tests.py    # 26 secret-scanner cases
.claude/scripts/tests/run-loop-tests.sh      #  6 unattended-run scenarios
.claude/scripts/tests/run-merge-tests.sh     # 10 local-merge cases
.claude/scripts/tests/run-mockup-tests.sh    #  8 approval-lock cases
.claude/scripts/tests/run-integrity-tests.sh # 11 dangling-reference cases
.claude/lib/tests/test-frontmatter.py        # 20 frontmatter-parser cases
.claude/lib/tests/test-gatelock.py           #  5 gate-lock cases
stacks/github/tests/run-risk-tests.py        # 32 risk-classification cases
stacks/github/tests/run-deliver-tests.sh     # 18 pull-request delivery cases

.claude/scripts/check-integrity.py           # cross-references resolve
.claude/scripts/spec-lint.py                 # specs meet the readiness checklist
.claude/scripts/spec-coverage.py             # every criterion has a test
.claude/scripts/build-map.py --check         # map is current
```

The guard suite is the one to extend when you find a hole. Every rule in it exists because something
got through.

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
gates and then claims success. All three are caught. The risk classifier — which decides what may merge
without review — is tested against 32 cases, including that an additive migration is auto-mergeable
while the same file containing `drop column` is not. Pull-request delivery is tested against 11 more,
of which ten are ways it should stop rather than merge.

Trellis has also been used on a real project by someone other than its author, which found three
further defects — six copies of one parser sharing a bug, an approval lock that missed brand assets,
and an integrity check reporting "all references resolve" while a reference dangled. All three were
the same shape, and that shape is now written into the `clean-code` skill.

**What still hasn't happened is a real overnight run against a real model.** The whole delivery loop
is verified against mocks. The first live run will find something — most likely around branch
protection, which the script reports but cannot fix.

Stack modules are the natural contribution: self-contained, they don't touch the core, and their value is
entirely in being current.

## Licence

MIT
