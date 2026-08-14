#!/usr/bin/env python3
"""Sweep every guard rule against ordinary developer work.

The test suite next door asks "does each rule catch what it should". This asks the opposite and more
easily forgotten question: does any rule fire on work that is entirely normal?

That failure is the one that does real damage. A rule which blocks nothing is discovered in minutes;
a rule which blocks ordinary commands trains everyone to route around the guard, and then it protects
nothing while still appearing to. Five separate rules in this file's history matched a word rather
than an act — `revoke`, `truncate`, `drop`, `delete from`, and the payload half of `obfuscation` —
and each was found only when someone hit it during real work.

So the corpus below is deliberately built from product vocabulary that collides with dangerous
keywords: the branch names, file paths, test filters and echoes a real project produces. Add to it
whenever a rule fires on something innocent. Anything it reports is a defect in a rule, not here.

Run it after changing any pattern:  .claude/hooks/tests/sweep-ordinary-work.py
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "..", "guard-production.py")

spec = importlib.util.spec_from_file_location("guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

RULES = guard.collect_rules()
if not any(r.get("stack") for r in RULES):
    print("note: no trellis.json here, so stack module rules are not loaded.")
    print("      run.py fabricates that list; this sweep only covers the base rules.\n")


def hits(command):
    normalised = guard.normalise(command)
    texts = normalised if isinstance(normalised, (set, list, tuple)) else [normalised]
    found = []
    for rule in RULES:
        for text in texts:
            if re.search(rule["pattern"], text, re.I):
                found.append(rule["id"])
                break
    return found


CORPUS = [
    # drag-and-drop, dropdowns, dropping a feature
    'git checkout -b agent/SPEC-041-drop-user-avatar',
    'cat src/components/DropTable.tsx',
    'rg "onDropTable" src/',
    'echo "drag to drop table rows into a new order"',
    'npm test -- --grep "drop user"',
    'echo "we should drop table support entirely"',
    'ls src/features/drop-schema/',
    # deleting things that are not rows
    'git checkout -b agent/SPEC-012-delete-from-cart',
    'echo "delete from cart"',
    'cat src/lib/cart/delete-from-cart.ts',
    'rg "deleteFrom" src/db/',
    'npm test -- --grep "delete from cart"',
    # updating and altering, in the product sense
    'echo "update user settings"',
    'git commit -m "update profile set-up flow"',
    'cat src/lib/alter-role-badge.tsx',
    'echo "alter user preferences in settings"',
    'echo "alter user avatar"',
    # granting and revoking, in the product sense
    'git checkout -b agent/SPEC-024-revoke-an-invite-link',
    'cat src/lib/invites/revoke.ts',
    'echo "grant access to the workspace"',
    'npm test -- --grep "revoke"',
    # truncating text
    'node -e "console.log(s.truncate(80))"',
    'cat src/lib/truncate.ts',
    'git checkout -b agent/SPEC-030-truncate-long-titles',
    'npm run build -- --truncate',
    # resetting and forcing, in the product sense
    'git reset --soft HEAD~1',
    'echo "hard reset the form state"',
    'rg "forceUpdate" src/',
    'cat src/lib/password-reset.ts',
    'git checkout -b agent/SPEC-055-force-logout-all-devices',
    # removing build output
    'rm -rf node_modules',
    'rm -rf ./dist',
    'rm -rf .next',
    'rm -f /tmp/scratch.txt',
    # reading state from the host
    'gh pr list',
    'gh pr view 12',
    'gh run view 99 --log-failed',
    'gh release list',
    'gh workflow list',
    # ordinary local database work
    'supabase start',
    'supabase status',
    'supabase db reset --local',
    'supabase gen types typescript --local',
    'psql postgresql://postgres@localhost:5432/dev -c "select 1"',
    'echo "DATABASE_URL=postgresql://postgres@localhost:5432/dev"',
    # other vocabulary collisions
    'cat src/lib/secrets-manager.ts',
    'rg "workflowRun" src/',
    'git checkout -b agent/SPEC-077-merge-duplicate-contacts',
    'cat src/features/release-notes/index.ts',
    # scripts named for production that READ from it — deploying and migrating are still blocked
    'node scripts/production-metrics.js',
    'bash scripts/prod-parity-check.sh',
    'python3 scripts/production_report.py',
    'node scripts/prod-health-check.js',
    'bash scripts/deploy-staging.sh',
    # writing a file and then running something else is not write-then-run
    'cat > vite.config.js <<EOF\nexport default {}\nEOF\nnpx vite build',
    'npm run build > build.log && cat build.log',
    'cat > notes.md <<EOF\nsome notes\nEOF\ncat notes.md',
]

# Nothing is accepted any more. write-then-run used to live here — it fired on scripts whose NAME
# mentioned production, including ones that only read from it. It now matches the act it is named
# for instead, so those commands are ordinary work and sit in the corpus above.
ACCEPTED = {}

failures = []
for command in CORPUS:
    found = hits(command)
    if found:
        failures.append((",".join(found), command))

print("Ordinary work that the guard blocks:")
if failures:
    for rule, command in failures:
        print("  %-24s %s" % (rule, command))
else:
    print("  (none)")

if ACCEPTED:
    print("\nAccepted false positives:")
    for command, rule in ACCEPTED.items():
        mark = "still blocked" if hits(command) else "NO LONGER BLOCKED — remove from this list"
        print("  %-24s %-42s %s" % (rule, command, mark))

print()
if failures:
    print("%d ordinary command(s) blocked — each one is a defect in a rule" % len(failures))
    sys.exit(1)
print("sweep: %d ordinary commands, none blocked" % len(CORPUS))
