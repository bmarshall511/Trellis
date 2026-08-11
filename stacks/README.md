# Stack modules

A stack module is everything Trellis knows about one technology. Modules are loaded **only** when a
project names them in `trellis.json`, so a project pays no context cost for technologies it doesn't use.

```json
{ "stacks": ["nextjs", "supabase", "vercel"] }
```

Nothing in the Trellis core knows any of these exist.

## Anatomy

```
stacks/<name>/
├── SKILL.md          required — what to know, loaded when the stack is active
├── guard.json        optional — dangerous command patterns this stack introduces
├── extract-map.py    optional — adds a section to docs/map/OVERVIEW.md
├── setup/            optional — config files copied in when the stack is adopted
└── VERIFIED          required — when this was last checked against reality
```

Copy `_template/` to start.

## SKILL.md

Standard skill frontmatter. The `description` decides when it loads, so write it as triggers — the
situations where this knowledge is needed — and nothing else.

Keep it to what is **specific and non-obvious**. General good practice already lives in the core skills;
repeating it here costs context in every session and teaches nothing.

What earns its place:

- **Version traps.** Config that silently does nothing in the wrong place. Options that moved between
  releases. Packages that were replaced.
- **Quota cliffs.** The specific number where a free tier stops working, and what happens when it does —
  a hard stop, silent degradation, or a surprise bill.
- **Correct patterns**, where the obvious approach is wrong.
- **Deprecations**, with what replaced them.
- **Gate wiring** — the exact commands this stack contributes to `trellis.json`.

What does not:

- Anything the official documentation says clearly and that hasn't changed
- General advice about testing, security or accessibility
- Tutorial material

## VERIFIED

One line: the date this module was last checked against reality, and against what.

```
2026-08-11 — checked against official docs, npm, and the vendor pricing page.
```

**This is the most important file in the module.** Technology knowledge decays fast. Over six rounds of
research building Trellis we found a deprecated package still being recommended, a config namespace that
silently did nothing, pricing wrong by two orders of magnitude, and a CLI setting ignored on older
versions — all within months.

A module older than about six months should be treated as a hypothesis, not a fact. Refresh it with
`/stack-add <name> --refresh` before relying on anything version-specific.

## guard.json

Dangerous command patterns this stack introduces, merged into the core guard when the stack is active.

```json
{
  "deny": [
    { "id": "unique-id", "pattern": "python regex", "reason": "what it would do and why that is bad" }
  ]
}
```

Patterns match case-insensitively against the command, both as written and with leading environment
assignments stripped. Prefer a pattern that is slightly too broad — a false positive costs one
human-run command; a false negative costs a database.

Test any pattern you add by appending cases to `.claude/hooks/tests/guard-cases.json` and running
`.claude/hooks/tests/run.py`. **A guard pattern with no test is not a guard** — the first version of the
core guard allowed everything, and only a test caught it.

## extract-map.py

Prints markdown to stdout. Whatever it prints becomes a section in the project map — a route list, an
exported-symbol index, a schema summary. Anything a reader would otherwise have to explore for.

It must be fast, dependency-free, and must never fail the build: exit 0 and print nothing if it can't
determine anything.

## setup/

Config files copied to the project root when the stack is adopted. These are the ones that would be
broken sitting in an empty repo — a test runner config pointing at a dev server, a linter importing a
plugin that isn't installed yet.

Include a `MANIFEST.json` mapping each file to its destination, and note anything the file expects to
already exist.

## Writing a new module

1. `cp -r _template <name>`
2. Research the technology **against primary sources** — official docs, the package registry, the
   vendor's own pricing page. Do not write from memory; that is exactly how the errors above happened.
3. Write `SKILL.md` covering only the specific and non-obvious.
4. Add guard patterns for anything destructive the tooling can do, **with tests**.
5. Record the gate commands the stack contributes.
6. Write `VERIFIED` with today's date and what you checked.

## Rules

- A module never assumes another module is present. Declare the relationship in `SKILL.md` instead.
- A module never edits Trellis core files.
- A module never weakens a core guard pattern. It may only add.
- If two modules disagree, the more specific one wins, and the conflict is documented in both.
