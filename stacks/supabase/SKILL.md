---
name: stack-supabase
description: Use when working with Supabase — database migrations, row-level security policies, auth, storage, the Supabase CLI, or local development. Also when wiring Supabase into a project or debugging a policy that is not behaving.
---

# Supabase

Only what is specific and non-obvious. General database, security and testing practice is in the core
skills.

## The commands that can destroy production

**`supabase db reset` with a remote target drops every user-created object in that database, with no
confirmation prompt.** With `--linked` or `--db-url` it is not a local operation. There is no "are you
sure".

**`supabase db push` targets whatever project is currently linked** — not whatever is in your `.env`. So
the question "which database am I about to change?" is answered by hidden CLI state, not by anything
visible in the repo.

Both are blocked by this module's `guard.json`. The blocking is a backstop; the real protection is below.

**Never link the repo.** `supabase link` persists a project reference locally, and from then on every
`db push` has a live target. A repo that is never linked has no path to production at all. Migrations
should reach production through your deployment pipeline, which links at run time using a credential that
never exists on the development machine.

If you find the project linked, treat that as a problem to fix, not a convenience to use.

## Backups — read this before you rely on any

**Supabase's backups do not include Storage objects. On any plan.** Uploaded files have no vendor-side
recovery path. If a project stores user uploads, it needs its own copy of them somewhere else, or those
files are one mistake from gone permanently.

**The free tier has no automatic backups at all.** Supabase's own documentation tells free-tier projects
to export their data themselves with `db dump`.

Point-in-time recovery is a paid add-on and considerably more expensive than it first appears — check the
current price plus any compute add-on it forces before recommending it. For a small project, scheduled
`pg_dump` to storage you control, plus soft deletes, covers more for far less.

## Row-level security

**Policies are the real authorisation boundary.** Anything the client can reach, it can query directly —
so a check that exists only in application code protects nothing.

- Enable RLS on every table holding user data. A table with RLS off and a public API is readable by anyone
- Write the deny case as a test, not just the allow case
- Policies run per row, so an unindexed column used in a policy turns every query into a scan
- `security definer` functions bypass RLS by design. Each one is a deliberate hole — set an explicit
  empty search path, gate it, and test that an unauthorised caller is refused

**Verify what is exposed.** Newly created tables have historically been auto-exposed through the data API
depending on schema and grants, and this behaviour has been tightening. Do not assume a table is private
because you did not mean to publish it — check.

## Migrations

- Forward-only. Never edit a migration that has been applied anywhere
- Expand then contract: add the new thing, migrate to it, and only remove the old thing in a later release.
  Never drop in the same change that stops writing
- Destructive statements — `drop table`, `drop column`, `truncate`, type narrowing, adding `not null`
  without a default — must be reviewed by a human before they reach production, and should fail an
  automated gate until they are
- Take a snapshot before applying anything to production. If the snapshot fails, the migration must not run

## Auth

Session handling in server-rendered frameworks is the part that is most often wrong and the part that
changes most between releases. Check the current official integration guide rather than copying an older
example — this API has been reworked more than once, and old examples still rank well in search.

Watch for: refreshing a session in the wrong place, cookie handling that works in development and fails in
production, and putting the authorisation check in routing rather than at the point data is accessed.

Service-role credentials bypass RLS entirely. They belong on a server, never in anything sent to a
browser, and never on a development machine that an agent shares.

## Local development

Local Supabase runs in Docker and is the correct target for all development and testing. `db reset`
against the local stack is safe and is the normal way to rebuild from migrations plus seeds.

Test suites must assert they are pointed at a local or explicitly-designated test database before running,
and abort otherwise. The destination is one environment variable away from production.

## Gates this stack contributes

Database policy tests, run against the local stack:

```json
{ "gates": { "test": "supabase test db" } }
```

Add a migration-safety check to CI that fails on destructive statements without an explicit human
approval marker.

## Verify before relying on

Pricing, free-tier limits, backup retention, and the auth integration pattern all change. Check the
vendor's own pages before making a recommendation that depends on a number or an API shape.
