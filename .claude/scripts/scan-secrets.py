#!/usr/bin/env python3
"""Trellis secret scanner.

Blocks credentials from reaching a commit. A secret committed once is a secret forever — it lives in
history and in every clone, so rotating it is the only real remedy. Catching it before the commit is the
only cheap moment.

Dependency-free and language-agnostic by design: this must work on a freshly downloaded repo before any
stack has been chosen or anything installed.

Usage:
  scan-secrets.py --staged      scan what is staged for commit (used by the pre-commit hook)
  scan-secrets.py [path ...]    scan specific files, or the whole tree if none given
"""
import base64
import math
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

# High-confidence credential shapes. Each has a distinctive prefix or structure, so false positives are
# rare enough that blocking on them is reasonable.
PATTERNS = [
    ("AWS access key id",        r"\bAKIA[0-9A-Z]{16}\b"),
    ("AWS secret access key",    r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}"),
    ("GitHub token",             r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("GitHub fine-grained PAT",  r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    ("Slack token",              r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("Stripe secret key",        r"\b[sr]k_(live|test)_[A-Za-z0-9]{20,}\b"),
    ("Anthropic key",            r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ("OpenAI key",               r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}\b"),
    ("Google API key",           r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("Supabase service key",     r"\bsb_secret_[A-Za-z0-9_-]{20,}\b"),
    ("SendGrid key",             r"\bSG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
    ("Resend key",               r"\bre_[A-Za-z0-9_-]{20,}\b"),
    ("Twilio key",               r"\bSK[0-9a-fA-F]{32}\b"),
    ("npm token",                r"\bnpm_[A-Za-z0-9]{30,}\b"),
    ("Private key block",        r"-----BEGIN (RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY( BLOCK)?-----"),
    ("JSON Web Token",           r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ("Database URL with password",
     r"\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis|amqp)://[^:@\s/]+:[^@\s/]{3,}@"),
    ("Generic assigned secret",
     (r"(?i)\b(api[_-]?key|secret|password|passwd|token|credential)\b\s*[:=]\s*"
     r"['\"][A-Za-z0-9/+_=-]{16,}['\"]")),
]

COMPILED = [(name, re.compile(pattern)) for name, pattern in PATTERNS]

# Values that match a pattern but are obviously not real.
#
# Deliberately NARROW. An earlier version suppressed anything containing "abcdef" or "1234567890",
# which silenced three of four genuine test keys -- a random credential contains such runs by chance.
# A false positive costs one comment; a false negative costs a rotated credential at best.
# Every token here must be something no random key would contain.
PLACEHOLDERS = re.compile(
    r"(?i)(example|placeholder|changeme|redacted|dummy|notarealkey|insert[_-]?your|"
    r"replace[_-]?(me|this)|your[_-](api|secret|token|key)|xxxx+|<[^>]{2,}>|\{\{|\$\{|"
    r"aaaaaa+|000000+)"
)

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", "target", "vendor",
    "__pycache__", ".venv", "venv", "coverage", ".turbo", ".cache",
    "test-results", "playwright-report",
}

# Binary and generated content — scanning it produces noise, not findings.
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf", ".zip", ".gz",
    ".tar", ".mp4", ".mov", ".mp3", ".woff", ".woff2", ".ttf", ".eot", ".lock",
}

# These necessarily contain things that look like credentials: the scanner's own patterns, and the
# fixtures that prove it works. Both are reviewed as source, not as configuration.
SELF = {
    ".claude/scripts/scan-secrets.py",
    ".claude/scripts/tests/secret-cases.json",
}

# Lockfiles are wall-to-wall high-entropy strings by design -- npm integrity hashes, content
# addresses, resolved URLs. Every one trips the entropy heuristic, and every one is meaningless.
# A Node project's very first commit produced 117 false positives before this existed, which would
# have taught the user to pass --no-verify on day one. A scanner people bypass protects nothing.
#
# Pattern matching still runs on them; only the entropy heuristic is skipped, so a real credential
# accidentally pasted into a lockfile is still caught by its prefix.
ENTROPY_EXEMPT_NAMES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock",
    "bun.lockb", "composer.lock", "gemfile.lock", "poetry.lock", "pdm.lock", "uv.lock",
    "cargo.lock", "go.sum", "packages.lock.json", "paket.lock", "podfile.lock", "flake.lock",
    "mix.lock", "pubspec.lock", "gradle.lockfile",
}

MAX_BYTES = 2_000_000


def shannon_entropy(value):
    if not value:
        return 0.0
    counts = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = len(value)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


# A Trellis spec slug: a branch name, or a path to a spec file. These trip the entropy heuristic
# often enough to matter, because the discriminator is entropy and not length — in one project
# `agent/SPEC-022-blocks-in-the-data-download` was flagged at 41 characters while
# `agent/SPEC-012-move-the-gate-lock-to-the-process-that-runs-the-gates` passed at 67. English
# kebab-case sometimes clears 4.2 and sometimes does not, which reads as random behaviour to anyone
# who has not read this function.
#
# Deliberately narrow. The tempting general rule — exempt anything that looks like hyphenated words —
# would exempt `sk_live_...` on the strength of the word `live`, and a passphrase on the strength of
# being words. This shape cannot be a credential: it is anchored, it names a spec, and every
# character is [a-z0-9/-] with SPEC- and digits in fixed positions.
SPEC_SLUG = re.compile(r"^(?:agent/|docs/specs/)?SPEC-\d+(?:-[a-z0-9]+)*(?:\.md)?$")


def looks_random(value):
    """A long, high-entropy string is a credential more often than it is anything else."""
    if len(value) < 24:
        return False
    if PLACEHOLDERS.search(value):
        return False
    if SPEC_SLUG.match(value):
        return False
    return shannon_entropy(value) > 4.2


def decoded_secret(line):
    """Base64 hides a credential from a plain pattern match. Decode long literals and re-check."""
    for candidate in re.findall(r"\b[A-Za-z0-9+/]{40,}={0,2}\b", line):
        try:
            text = base64.b64decode(candidate, validate=True).decode("utf-8", "ignore")
        except Exception:
            continue
        for name, regex in COMPILED:
            if regex.search(text):
                return name
    return None


def staged_files():
    try:
        out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                             cwd=ROOT, capture_output=True, text=True, timeout=15)
        return [p for p in out.stdout.splitlines() if p]
    except Exception:
        return []


def walk_tree():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            found.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    return found


def scan_file(rel_path):
    if rel_path in SELF:
        return []
    entropy_ok = os.path.basename(rel_path).lower() not in ENTROPY_EXEMPT_NAMES
    if os.path.splitext(rel_path)[1].lower() in SKIP_EXTENSIONS:
        return []
    full = os.path.join(ROOT, rel_path)
    try:
        if os.path.getsize(full) > MAX_BYTES:
            return []
        with open(full, encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except Exception:
        return []

    findings = []
    for number, line in enumerate(content.splitlines(), 1):
        if len(line) > 4000:
            continue
        if re.search(r"(?i)\ballow[_-]?secret\b|\btrellis:ignore-secret\b", line):
            continue  # explicit, reviewable opt-out

        for name, regex in COMPILED:
            match = regex.search(line)
            if match and not PLACEHOLDERS.search(match.group(0)):
                findings.append((number, name, match.group(0)))
                break
        else:
            name = decoded_secret(line)
            if name:
                findings.append((number, f"{name} (base64-encoded)", "<encoded>"))
                continue
            if not entropy_ok:
                continue
            for value in re.findall(r"['\"]([A-Za-z0-9/+_=-]{24,})['\"]", line):
                if looks_random(value):
                    findings.append((number, "high-entropy string", value))
                    break
    return findings


def redact(value):
    if len(value) <= 12:
        return value[:2] + "…"
    return f"{value[:6]}…{value[-4:]}"


def main():
    args = [a for a in sys.argv[1:] if a != "--staged"]
    if "--staged" in sys.argv:
        targets = staged_files()
        scope = "staged changes"
    elif args:
        targets = args
        scope = "%d file(s)" % len(args)
    else:
        targets = walk_tree()
        scope = "the whole tree"

    total = 0
    for rel_path in targets:
        for number, name, value in scan_file(rel_path):
            if total == 0:
                print("Possible credentials found — commit blocked.\n", file=sys.stderr)
            total += 1
            print("  %s:%d" % (rel_path, number), file=sys.stderr)
            print(f"    {name}: {redact(value)}", file=sys.stderr)

    if total:
        print(
            "\n%d finding(s) in %s.\n"
            "\nIf any of these is a real credential, it must be REMOVED and ROTATED. Deleting the line\n"
            "is not enough once it has been committed — it stays in history and in every clone.\n"
            "\nIf a finding is a false positive, add `trellis:ignore-secret` in a comment on that line so\n"
            "the exception is visible in review." % (total, scope),
            file=sys.stderr,
        )
        return 1

    print(f"secrets: clean ({scope})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
