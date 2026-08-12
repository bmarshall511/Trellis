---
name: stack-github
description: Use when publishing an unattended run as a pull request, setting up branch protection or CI on GitHub, deciding whether a change may merge without review, or working with the gh CLI.
---

# GitHub

Only what is specific and non-obvious. General practice is in the core skills.

## The half of the loop the agent does not hold

A run produces a **local, unpushed branch** and stops. Publishing, reviewing and merging are separate
steps the agent cannot perform — `gh pr merge`, `gh pr review`, `gh secret set` and `gh ruleset` are all
on its deny list.

This is not a formality. An agent that can merge its own work has no review, and one that can edit
branch protection has no gates. Keep the deny list intact even when it is inconvenient.

Publish with `stacks/github/scripts/publish-run.sh <spec-id>`. It refuses anything whose run outcome was
not `DONE`, and refuses `TAMPERED` outright.

## Stronger than a deny list

If you set up a **GitHub App** for the agent's pushes, grant it `Contents`, `Pull requests` and `Issues`
write — and deliberately **not** `Workflows`. GitHub then rejects, at the git protocol level, any push
touching `.github/workflows/**`. That turns "the agent must not edit CI" from an instruction it might
forget into something it cannot do.

A useful side effect: because the App authors the pull request, you are not its author, so GitHub's
self-approval block does not apply and requiring one approving review becomes possible for a solo
developer. That gives you a dial — require an approval while you are learning to trust the loop, drop
it later — rather than an all-or-nothing choice.

## Risk classification

`risk-policy.json` decides what may merge without a human. It is checked in, so the policy is reviewable
and its history is visible.

The question it answers is **not** "is this change correct" — the gates answer that. It is "if this
change is wrong, how bad is it, and can it be undone". A green test suite says nothing about whether a
dropped column can be recovered.

It fails closed: an unreadable policy, an unreadable diff, or any error produces `needs-human`.

Content matters as well as paths. An additive migration is auto-mergeable; the same file containing
`drop column` is not. `delete from x where id = 1` is auto; `delete from x` is not. `not null default ''`
is auto; a bare `not null` is not, because it fails on existing rows and takes a lock.

Run it yourself with `stacks/github/scripts/classify-risk.py`. Do not weaken a rule to get a change
through — if a rule is wrong, change it in its own reviewed commit, never in the change it is blocking.

## CI shape and cost

**One job with sequential steps, not several parallel ones.** GitHub bills **per job, rounded up to the
whole minute**, so five twenty-second jobs cost five minutes while one job costs one. Sharding optimises
wall-clock time; you are paying for jobs.

Order matters: the dependency-free structural checks (integrity, secrets, spec lint, coverage) run first
and take seconds, so a structural problem fails before anything slow starts.

Public repositories get free minutes on standard runners; private ones have a monthly allowance. That
asymmetry is worth knowing before choosing repository visibility.

## Branch protection

Required status checks are what make `gh pr merge --auto` mean anything — without them there is nothing
for the merge to wait on, and the whole gate is decorative.

**Verify this on your own repository before relying on it.** Availability of rulesets and protected
branches has varied by plan and by repository visibility, and it has changed more than once. If your
repository does not offer them, the auto-merge half of this module does not work and you should review
every run by hand.

## Gates this stack contributes

Copy `setup/workflows/verify.yml` to `.github/workflows/verify.yml`. It runs the Trellis structural
checks plus whatever gates `trellis.json` declares, and labels a pull request `needs-human` when the
classifier says so.

## Verify before relying on

Plan requirements for rulesets, Actions minute allowances, and auto-merge semantics all change. Check
GitHub's own documentation rather than trusting this file's summary of them.
