# Trellis — Build Plan

Rewritten 2026-08-11. The previous version planned an application — marketing pages, admin, collections,
media, PWA. That is superseded: **Trellis contains no application**. See [DECISIONS.md](DECISIONS.md) §1.

Research is complete: 6 rounds, ~35 briefs.

---

## Governing principle

Trellis is a skeleton, not an application. It provides *process*, *standards* and *guardrails*, and gets
out of the way. What a project is built with is decided during that project, by the agent, from that
project's requirements.

- **Almost everything is opt-in.** A project turns on what it needs.
- **The only non-negotiables protect you:** the production guardrails, and the spec → test → gate loop.
- **Technology knowledge lives in stack modules**, loaded only when used, and dated so staleness is visible.

---

## Phase 1 — Core ✅ complete

| | Count | |
|---|---:|---|
| Skills | 10 | spec-authoring, stack-selection, testing, accessibility, security, clean-code, component-design, feedback-and-performance, mockups, documentation |
| Agents | 3 | spec-auditor, coverage-auditor, implementation-reviewer — all read-only |
| Commands | 9 | spec-new, spec-next, spec-status, spec-verify, mockup, handoff, map, audit, stack-add |
| Hooks | 4 | production guard, verify gate, session start, pre-compact handoff |
| Scripts | 3 | build-map, mockup approval, integrity check |
| Guard tests | 51 | all passing |

Working and verified: the production guard blocks 31 dangerous command shapes while allowing their safe
equivalents; the verify gate stops the agent claiming completion while gates are red; mockup approval is
void the moment the mockup *or its tokens* change; the integrity checker catches dangling references,
non-executable hooks, and untested guard rules.

---

## Phase 2 — Baseline configuration · ~1 session

The stack-independent things that should be active the moment the repo is downloaded, because they hold
for any project in any language.

- Formatting and editor config
- Git hooks that run the declared gates before commit — and cannot be bypassed silently
- Secret scanning before commit, so a credential can never reach a first commit
- `.gitignore` covering credentials, environment files and build output
- A `trellis.json` starter and a validator that runs it against the schema

Small, and it closes the gap where a brand-new project has no protection until its stack is chosen.

## Phase 3 — Prove it ⭐ · ~2 sessions

**The most important remaining phase.** Use Trellis to build something small and real, start to finish,
and watch where it breaks.

Pick a genuinely trivial project. Then, without shortcuts: interview → stack recommendation → foundations
mockup → spec → implementation → gates → verification.

What this is actually testing:

- Does the interview find the ambiguity, or does the agent still guess?
- Does the readiness checklist reject a spec that is not ready, or wave it through?
- Does the verify gate catch a real failure, or only synthetic ones?
- Does `coverage-auditor` catch a test that would pass while the behaviour is broken?
- Is the whole thing *pleasant*, or so heavy that skipping it is tempting?

Every skill so far is a hypothesis about what makes an agent produce good work. This is the first
evidence. Expect to rewrite several of them afterwards — that is the point of doing it before building
more.

## Phase 4 — Autonomous runs · ~3 sessions

Unattended implementation, ending green or in a `BLOCKED` report naming one specific question.

**Core** (host-agnostic): the run wrapper, the settings profile that denies asking questions, bounded
repair, the run report, and notification on finish or block.

**`stacks/github/`**: pull request creation, watching checks, the risk classification that decides what
may merge unattended, and auto-merge. Host-specific, so it belongs in a module rather than the core.

Not before phase 3. Automating a workflow you have not run manually automates whatever is wrong with it.

## Phase 5 — Stack modules · ~2 sessions

Seed the technologies you actually use, from the research already done: `nextjs`, `tailwind`,
`playwright`, `storybook`, `vercel`, `resend`.

Each gets version traps, quota cliffs, correct patterns, deprecations, guard patterns **with tests**, and
a dated `VERIFIED`.

The research is current as of today, which is exactly why this should not wait long.

## Phase 6 — Staying current · ~1 session

- `/stack-add <name> --refresh` — re-research a module and report what changed, especially deprecations
  and repricing
- A staleness warning when a module's `VERIFIED` date is more than six months old
- Getting-started documentation, written by using it rather than by imagining it

---

## Cut, and why

| Cut | Reason |
|---|---|
| App scaffold, admin, collections, media, PWA, SEO modules | Trellis contains no application |
| The `create-trellis` CLI | You download the repo |
| Reference app | Nothing to demo. The scripts have their own tests |
| Root-owned settings needing `sudo` | Must be self-contained |
| Supabase point-in-time recovery | ~78× the cost of self-managed backups, and covers no user media |
| Chromatic | Playwright does visual comparison for free |
| Electron / Tauri | PWA install, zero build pipeline |
| Rich text editor | Markdown |

---

## Effort

**~9 sessions remaining.** Phase 3 is the one that matters — everything after it is informed by what it
finds, and building phases 4–6 first would mean building on untested assumptions.

## Cost

$0. It is a repo. What a project built with it costs depends on that project.
