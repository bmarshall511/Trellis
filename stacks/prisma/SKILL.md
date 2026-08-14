---
name: stack-prisma
description: Use when working with Prisma — schema changes, migrations, seeding, the Prisma CLI, or connecting to a database through Prisma Client. Also when a migration behaves unexpectedly, or when deciding how a schema change reaches production.
---

# Prisma

Only what is specific and non-obvious. General database, security and testing practice is in the core
skills.

## The target is invisible

Every Prisma command reads `DATABASE_URL` from the environment. There is no `--local` flag and no
linked-project state. So `npx prisma migrate reset` is character-for-character identical whether it
wipes a scratch database or production — the difference lives in a `.env` file, or in whatever the
shell happened to export.

This is the single most important thing about working with Prisma safely, and it is why the guard
requires the target to be stated in the command:

```bash
DATABASE_URL=postgresql://user@localhost:5432/dev npx prisma migrate reset
```

That is more typing. It is also the only way the command says what it will do to.

## The commands that can destroy a database

**`prisma migrate reset` drops the database and recreates it from migrations.** With `--force`, or in
any non-interactive shell, there is no confirmation. An unattended run is a non-interactive shell.

**`prisma db push --accept-data-loss` drops the columns and tables the schema no longer describes.**
The flag exists specifically to suppress the warning that would otherwise stop it.

**`prisma db push` writes the schema directly with no migration file**, so nothing records what
changed. Useful while prototyping, wrong once anything else depends on the schema.

**`prisma db execute` runs arbitrary SQL**, normally from a file. Every SQL rule in the core guard is
bypassed by putting the statement in that file rather than in the command.

**`prisma migrate resolve` rewrites migration history** to mark a migration applied or rolled back
without running it. Nothing is destroyed at the time, which is what makes it easy to wave through —
the database and the history now disagree, and the next deploy is the one that fails.

## Migrations

Migrations reach production through the deployment pipeline, never from a developer machine. The
pipeline runs `prisma migrate deploy`, which applies pending migrations and nothing else — it never
resets, and never prompts.

**A migration that adds a `NOT NULL` column to a populated table will fail**, and on a large table
locks it while it tries. Add the column nullable, backfill, then add the constraint — three
migrations, not one. The risk classifier holds exactly this shape for review.

**Never edit a migration that has been applied anywhere.** Prisma records a checksum; an edited
migration makes the history invalid on every database that already ran it.

## Seeding

Seed scripts run with the same `DATABASE_URL` as everything else, and a seed that truncates before
inserting is a production-wiping script wearing ordinary clothes. Write seeds to be additive and
idempotent — upsert on a natural key rather than clearing the table first.

Seeds are also usually invoked through an npm alias (`npm run db:seed`), which hides the underlying
command. The guard resolves aliases, but a person reading the command will not.

## Client

**`PrismaClient` must be a singleton in development.** Next.js hot reload re-executes modules, and a
new client per reload exhausts the connection pool within minutes. Attach it to `globalThis` outside
production.

**Prisma does not enforce row-level security.** If the database has RLS policies, Prisma connects as
a role those policies apply to — or, if it connects as the owner, it bypasses them entirely. Know
which; the failure is silent either way.
