# Framework — Confirmed Decisions

Running log of decisions Ben has explicitly confirmed. Anything not in here is still open.
Research briefs live in the session scratchpad (`scratchpad/research/`, 30+ briefs, rounds 1–6).

**Status:** research complete (6 rounds, ~35 briefs). Core build in progress — see [PLAN.md](PLAN.md).
**Last updated:** 2026-08-11

---

## 1. What we're building

> **Name: Trellis.**
>
> **Trellis contains NO application.** It is a repo you download that holds the Claude layer — rules,
> skills, commands, agents, hooks — plus the spec system, mockup workflow, session handoff, repo map,
> safety rails, and testing/linting configuration. Nothing about any app is pre-built or assumed.
> No CLI. You download it, open Claude, and describe what you want to build.
>
> The stack (Next.js, Tailwind, Supabase, Resend, Vercel) is a **strong recommendation** carried in the
> skills, not a fixture. A project can deviate and the skills adapt.
>
> Stack-specific configs (Playwright, ESLint, TypeScript, Storybook, package scripts) live in `setup/`
> as finished files and move to the root when a project starts — they'd be broken sitting in an empty repo.
> Stack-independent config (formatting, git hooks, secret scanning) is active on download.

| # | Decision | Confirmed |
|---|---|---|
| 1.1 | ~~Three deliverables: template repo + plugin + CLI~~ **SUPERSEDED.** One repo, downloaded directly. No CLI, no app scaffold | ✅ |
| 1.2 | Framework repo is **public / open source** | ✅ |
| 1.3 | Repo will live at **https://github.com/bmarshall511/Trellis**. Ben creates it when ready — do not create or push to it | ✅ |
| 1.4 | **Upstream framework updates must flow into projects already created from it** | ✅ |
| 1.5 | The agent layer must be installable onto Ben's *existing* projects, not template-only | ✅ |
| 1.6 | ~~Ships a reference app~~ **SUPERSEDED** by 1.1 — Trellis contains no application, so there is nothing to demo. Its own guard/map/mockup scripts are covered by their own tests instead | ✅ |
| 1.7 | **Name: Trellis** | ✅ |

## 2. Application shape

| # | Decision | Confirmed |
|---|---|---|
| 2.1 | **One Next.js app**, three surfaces: public marketing (`/`), authenticated app (literal `/app` prefix), admin | ✅ |
| 2.2 | Three route groups `(marketing)` / `(auth)` / `(app)`, each with its own root layout; no top-level `src/app/layout.tsx` | ✅ (recommended, adopted) |
| 2.3 | **Not API-first.** Cookie sessions + a Data Access Layer in `src/server/**` | ✅ |
| 2.4 | Capacitor: **deferred indefinitely.** Adopt ~12 cheap constraints that keep the door open (typed service layer, safe-area tokens, custom image loader, etc.) but build no module until a real app asks. Never use Capacitor's remote-URL mode — it turns one XSS into camera and filesystem access | ✅ |
| 2.4b | **Desktop = PWA install. Electron and Tauri are written non-goals.** Electron's support window is ~6 months — a recurring pipeline chore for features Ben doesn't need | ✅ (recommended, adopted) |
| 2.5 | **No external CMS.** App-specific structures (tags, taxonomies, categories) are Supabase tables with admin CRUD | ✅ |
| 2.6 | Marketing copy lives **in code**; deploys to change it are fine. Marketing branding is therefore **build-time** | ✅ |
| 2.7 | Markdown when rich text is needed (rare). **No WYSIWYG editor** | ✅ |
| 2.8 | Ownership column is **`account_id`**, not `org_id` or `user_id`. Every project ships the account shape; `personal` mode auto-creates an account-of-one and hides all sharing UI; `teams` mode turns the UI on with **zero migration** | ✅ |
| 2.9 | Auth: users + **simple user/admin roles** | ✅ |
| 2.10 | **Offline writes are required** — users create/edit offline, sync on reconnect. Scope line still open | ✅ (scope ⬜) |
| 2.11 | User-uploaded **images and video**; video typically 2–3 min | ✅ |
| 2.12 | Stripe = optional module (when needed). i18n = optional module | ✅ |

## 3. Configuration & secrets

| # | Decision | Confirmed |
|---|---|---|
| 3.1 | Runtime config + third-party API keys live **in Postgres**, edited from an **admin UI**, no redeploy | ✅ |
| 3.2 | Config tables live in an **`app_private` schema** that PostgREST does not expose | ✅ (recommended, adopted) |
| 3.3 | Secrets use **app-layer envelope encryption** (AES-256-GCM), **not Supabase Vault** — Vault's root key lives with Supabase, so a leak yields plaintext | ✅ (recommended, adopted) |
| 3.4 | Secrets are **write-only**. No reveal endpoint exists in the codebase, ever | ✅ (recommended, adopted) |
| 3.5 | **Env var floor accepted (~5):** Supabase URL, publishable key, secret key, `CONFIG_ROOT_KEY`, site URL. A lint rule rejects any *new* env var without a config-registry entry | ✅ |
| 3.6 | **First-run setup wizard** — a fresh deploy walks the owner through creating the first admin and entering keys | ✅ |

## 4. Database safety (highest priority — Ben has lost a production DB to an agent before)

| # | Decision | Confirmed |
|---|---|---|
| 4.1 | Principle: production must be **unreachable by the agent, not merely forbidden**. Instructions in markdown are not a control | ✅ |
| 4.2 | **Ben's machine CAN reach production. The agent CANNOT** — same machine, same shell | ✅ |
| 4.3 | **Read-only is sufficient** for Ben's production access (post-deploy verification + debugging). No write-escalation ritual needed | ✅ |
| 4.4 | Production credentials are **brokered, never ambient** — Keychain/1Password behind a wrapper command, never in a file or env var, because Claude Code's Bash tool inherits the shell environment | ✅ (design) |
| 4.5 | The broker command, `security`, `op`, `supabase link`, `supabase db push`, and non-localhost `psql`/`curl` are on the agent's **hard deny list**. Allowlist over denylist at the `PreToolUse` hook | ✅ (design) |
| 4.6 | Migrations **always auto-apply on merge** — and therefore the gate lives at the PR: destructive DDL fails a required check, so the PR cannot auto-merge until Ben approves | ✅ |
| 4.7 | **Staging DB: a second free Supabase project**, permanent, that all preview deployments point at. Previews must never hold production keys | ✅ |
| 4.8 | Test bootstrap asserts the target DB is localhost/staging **and** that a sentinel `environment='test'` row exists, or the suite aborts | ✅ (design) |
| 4.9 | Pre-migration snapshot taken automatically before any auto-applied migration | ⬜ (round 6) |
| 4.10 | **The framework must be self-contained — no machine-level `sudo` install step.** The root-owned managed-settings file is REJECTED. Gap closed instead by: agent cannot push to main, and CI rejects any agent-authored PR touching a guard file | ✅ |
| 4.11 | **Delete means delete, with a 30-day trash.** User clicks delete → hidden immediately and permanently erased after 30 days (Gmail/Dropbox model). Gives Ben an undo window without leaving data around forever. Throwaway records (sessions, caches) skip the trash | ✅ |
| 4.12 | **No special GDPR erasure function needed** — an erasure request just empties that user's trash immediately. 4.11 dissolves this problem | ✅ |
| 4.13 | Supabase **Free + self-built nightly encrypted backup**; move to paid only when an app has real users. **Never buy PITR** (~$140/mo) for a solo project | ✅ |
| 4.14 | **The agent CAN read production so it can debug independently.** A dedicated Postgres role with only `SELECT` granted, `default_transaction_read_only = on` at the role level, a statement timeout, and query logging. Enforced by Postgres, not by a hook — the role has no write grants to route around. Write credentials still do not exist on the machine. Accepted consequence: real user data enters the agent's context during debugging | ✅ (Ben reaffirmed twice; earlier "no agent read path" recommendation overruled) |
| 4.15 | Never `supabase db reset` with a remote target — it drops all user-created entities in the remote database **with no confirmation prompt**. Never allow the bare wildcard form | ✅ (correction) |
| 4.16 | Production hosts are network-denied at the sandbox level, not merely absent from an allow list | ✅ (correction) |
| 4.17 | Unattended runs use `--permission-mode dontAsk`. **Never `bypassPermissions`** — it permits protected-path writes, so an agent could delete its own guardrails | ✅ (correction) |

## 5. Delivery loop

| # | Decision | Confirmed |
|---|---|---|
| 5.1 | **Spec authoring is interactive and interrogative; spec execution is fully autonomous and unattended.** All ambiguity resolved at authoring time so implementation needs zero questions | ✅ |
| 5.2 | Two legal endings: green with all acceptance criteria met, or a **`BLOCKED` report naming one specific question**. Never guess, never half-ship | ✅ |
| 5.3 | Autonomous runs execute **locally on Ben's Mac** (covered by Max plan; has Docker + local Supabase). Mac is normally always awake | ✅ |
| 5.4 | Run must be **green locally before opening the PR** — CI is confirmation, not discovery | ✅ (design) |
| 5.5 | The agent pushes as a **GitHub App with no `Workflows` permission**, so GitHub rejects at the protocol level any push touching `.github/workflows/**`. Also makes Ben a valid reviewer of the App's PRs | ✅ (recommended, adopted) |
| 5.6 | **Risk gate**: a checked-in policy classifies the diff. Auth/RLS/security headers/destructive migrations/new deps/CI config → `needs-human`. Everything else auto-merges | ✅ |
| 5.7 | **Bounded repair**: max 2–3 attempts on CI failure, never applied to a policy gate, then stop and report | ✅ |
| 5.8 | **Hard deny on adding dependencies** during an unattended run — a spec needing a new library goes BLOCKED | ✅ (recommended, adopted) |
| 5.9 | Queue **stops entirely on the first BLOCKED** rather than skipping ahead | ✅ |
| 5.12 | **Two-process split for overnight runs.** The *implementer* runs `claude -p --permission-mode dontAsk` — it physically cannot ask questions, and its only non-green ending is `BLOCKED.md`. A separate interactive *orchestrator* session with remote control forwards questions to Ben's phone and waits indefinitely; he taps an answer and the run resumes. $0/mo | ✅ (recommended, adopted) |
| 5.13 | Notifications: BLOCKED/FAILED only, plus one morning digest. Successes are visible in the PR list — a channel you mute is a channel you don't have | ✅ (recommended, adopted) |
| 5.10 | Ben chooses at run time which specs and how many; the agent asks to clarify | ✅ |
| 5.11 | **Never use `claude -p --bare`** — it skips hooks (killing the Stop-hook guarantee) *and* forces API billing off the Max plan | ✅ |

## 6. Quality bars

| # | Decision | Confirmed |
|---|---|---|
| 6.1 | **Coverage contract**: every spec has numbered acceptance criteria; every AC maps to ≥1 automated test; CI fails on an unmapped AC. Level (unit / component / E2E) chosen per AC, E2E reserved for user journeys | ✅ |
| 6.2 | Every UI state (loading / empty / error / success / offline) gets a Storybook story with a11y + visual snapshot | ✅ |
| 6.3 | **WCAG AA everywhere + a named AAA subset**: 7:1 contrast on user-facing surfaces, enhanced focus, larger targets, no timing. Explicitly **excludes** 1.2.6 Sign Language and 1.2.7 Extended Audio Description | ✅ |
| 6.4 | Captions (1.2.2) is **Level A, not AA** — earlier rounds had this wrong | ✅ (correction) |
| 6.5 | Admin contrast: AA rather than 7:1 on dense data tables | ⬜ recommended |
| 6.6 | GDPR consent banner required by default | ✅ |
| 6.7 | **Tiered clarification policy**: hard-stop for schema / auth / external side effects / new deps / user-facing copy / spec deviation / deletions; everything else proceeds and is written to an assumption log reviewed in batch | ✅ |

## 7. Mockups

| # | Decision | Confirmed |
|---|---|---|
| 7.1 | **Tier 1 — design foundations** (tokens, ramps at 7:1, type scale, spacing, motion, primitives): reviewed as a style-tile page and *becomes* the implementation | ✅ |
| 7.2 | **Tier 2 — feature mockups**: static HTML built from the real tokens, **reference-only, not promoted to implementation**. Committed forever | ✅ |
| 7.3 | Mockups are committed and kept for reference | ✅ |
| 7.4 | **3 design directions generated per project** to choose from | ✅ |
| 7.5 | Approval is a **SHA-256 hash lock** over artifacts + tokens + commit, not a file-existence check — the existing gate is forgeable | ✅ (correction, adopted) |
| 7.6 | After implementation, a **visual diff compares the shipped page to the approved mockup** — this is what makes committing mockups pay off | ✅ (design) |

## 8. Environment & tooling

| # | Decision | Confirmed |
|---|---|---|
| 8.1 | Solo developer, always. Claude **Max** plan. macOS. Docker available | ✅ |
| 8.2 | **Free tiers strongly preferred**; pay only where clearly worth it. Round-1 model came out at $155–280/mo — being re-costed in round 6 | ✅ (tension) |
| 8.3 | **Local-first quality gates**, minimal GitHub Actions minutes | ✅ |
| 8.4 | CI shape: **2 jobs, zero shards** — GitHub bills per job rounded up to the whole minute, so the original 16–19 job fan-out cost ~4× the free allowance | ✅ (correction) |
| 8.5 | Public framework repo *can* fan out (public repos get free unlimited standard runners); private project repos get the lean 2-job shape | ✅ |
| 8.6 | `permissions.defaultMode: "default"` pinned in `~/.claude/settings.json` (was unset) — set 2026-08-11 | ✅ done |
| 8.7 | Get `.claude/` **out of the project repo** into the plugin. Boundary: anything a GitHub workflow executes lives in the repo; anything only Claude reads lives in the plugin | ✅ (recommended, adopted) |
| 8.8 | Notification/monitoring of overnight runs — Ben uses the Claude mobile app; whether local sessions are visible there is under verification | ⬜ (round 4) |
| 8.9 | Project repos public vs private (GitHub Pro at $4/mo is a hard dependency if private — rulesets are unavailable on Free) | ⬜ |

## 9. Known corrections (things earlier rounds got wrong)

- `@react-email/components` is **npm-deprecated**
- `cva@1.0.0-beta.8` **does not exist** on npm
- `reactCompiler`, `taint`, `useOffline`, `cacheComponents` are **top-level** Next.js config keys, not `experimental.*` — wrong namespace **silently no-ops**
- Supabase **PITR is ~$140/mo**, not $25–45
- **Supabase backups never include Storage objects on any plan** — no recovery path for user media as designed. Largest unmitigated risk
- Session replay on by default is a **UK/EU consent violation** (UK PECR rewritten 2026-02-05, DUAA 2025)
- FAQPage / HowTo structured data are **gone** from Google's rich-results gallery
- Vercel image optimizer + UGC = HTTP 402 in week one (5,000/mo Hobby quota); UGC must never touch the optimizer

## 10. Calendar

- **2026-09-01** — Sonnet 5 pricing $2/$10 → $3/$15; compounds with a tokenizer on 4.7+ models emitting ~30% more tokens
- **2026-10-30** — Supabase Data-API grants enforced on all existing projects

---

## Still open

Offline-write scope line · project repos public vs private · approve-every-PR for month one then drop to
zero · analytics pre-consent vs gated · captions gate for end-user uploads · R2 from day one vs
Supabase-first · discard end-user originals · admin impersonation · merchant of record

**Note:** most of the above were decided when Trellis was going to contain an application. They are now
*per-project* questions, answered when a project is built — not framework decisions. They are kept here
only as research findings worth recalling when a project raises them. See [PLAN.md](PLAN.md).
