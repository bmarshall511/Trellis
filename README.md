# Trellis

<https://github.com/bmarshall511/Trellis>

A structure that guides how software gets built, so the result is clean, tested, performant,
accessible and maintainable — regardless of what it's built with.

Trellis contains **no application and no stack**. It is the process, the standards and the guardrails.
What a project is built with gets decided during that project, by the agent, based on what the project
actually needs.

## Using it

Download this repo. Open Claude. Describe what you want to build.

```
claude
> I want to build <describe it>
```

The agent interviews you, recommends a stack for those requirements, writes specs, produces designs for
your approval, and then builds — with every quality gate enforced automatically.

## What's in here

```
.claude/skills/     the standards and the process, written as principles
.claude/commands/   spec new, spec next, spec status, mockup, handoff, map, audit
.claude/agents/     independent reviewers and auditors
.claude/hooks/      guardrails that run automatically
docs/specs/         your specs
docs/mockups/       approved designs, kept for reference
docs/map/           auto-generated overview so the agent doesn't re-read the codebase
stacks/             knowledge modules, loaded only for the technologies a project uses
setup/              config files staged until a project's stack is chosen
trellis.json        what this project is and what it's built with
```

## The three things Trellis actually does

**1. Nothing gets built from a guess.**
Specs are written interactively — the agent keeps asking until nothing is ambiguous. Implementation then
runs without questions. A run either finishes green or stops and writes down the single thing it couldn't
resolve. It never assumes.

**2. Nothing merges without proof.**
Every acceptance criterion in a spec must map to a test. Type checking, linting, tests and — where there's
a user interface — accessibility and performance all have to pass. The agent cannot mark work complete
while any gate is red.

**3. Production cannot be damaged.**
An agent never holds write access to a production database. This is enforced by the credentials that exist,
not by an instruction it might forget.

## Project types

Trellis adapts to what you're building. A project declares its type in `trellis.json`, and parts of the
process switch on and off accordingly.

| | Specs | Tests | Mockups | Accessibility |
|---|---|---|---|---|
| Application with a UI | ✓ | ✓ | ✓ | ✓ |
| API or service | ✓ | ✓ | — | — |
| CLI tool | ✓ | ✓ | — | — |
| Library | ✓ | ✓ | — | — |

## Stack modules

`stacks/` holds what Trellis knows about specific technologies — correct patterns, version traps, cost
cliffs, and the quality gate each one implements. A module is loaded only if `trellis.json` says the
project uses it. A project using none of them still gets the entire core.

Technology knowledge goes stale quickly. Each module records when it was last verified and can refresh
itself.

See [stacks/README.md](stacks/README.md) to add one.

## The gate contract

Trellis defines *what* must be verified. Stack modules decide *how*.

Every project exposes the same commands, whatever it's written in:

| Command | Must |
|---|---|
| `verify:types` | Fail on any type error |
| `verify:lint` | Fail on any lint error |
| `verify:test` | Run the full suite, fail on any failure |
| `verify:a11y` | *(UI only)* Fail on any accessibility violation |
| `verify:perf` | *(UI only)* Fail on any performance budget breach |
| `verify` | All of the above, in order, stopping at the first failure |

A gate that isn't applicable is declared absent in `trellis.json`, not silently skipped.

## Status

Under construction. See [PLAN.md](PLAN.md) for the build order and [DECISIONS.md](DECISIONS.md) for
every decision made and why.
