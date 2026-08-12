#!/usr/bin/env python3
"""Trellis repo map builder.

Generates docs/map/OVERVIEW.md — a compact picture of the project that an agent reads at the start of a
session instead of exploring the codebase file by file.

Design constraints, in order:

  1. It must be cheap to read. Every token here is paid for in every session that loads it. Breadth over
     depth: say what exists and where, not what it does line by line.
  2. It must be stack-agnostic. Anything language-specific comes from a stack module's extractor.
  3. It must never be stale without saying so. A confidently wrong map is worse than no map, because the
     agent trusts it instead of looking.

Run: .claude/scripts/build-map.py [--check]
  --check exits non-zero if the map is out of date, for use as a gate.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from datetime import datetime, timezone

from frontmatter import parse_file

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
MAP_DIR = os.path.join(REPO_ROOT, "docs", "map")
MAP_FILE = os.path.join(MAP_DIR, "OVERVIEW.md")

# Directories that are never interesting to a reader of the map.
SKIP_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "out", "target", "vendor",
    "__pycache__", ".venv", "venv", ".pytest_cache", "coverage", ".turbo",
    ".cache", "tmp", ".DS_Store", "test-results", "playwright-report",
    ".idea", ".vscode", ".svelte-kit", ".nuxt", ".parcel-cache",
}

# The map lists everything except itself. Counting its own output means the file set changes every
# time it runs, so --check can never pass.
SELF_EXCLUDE = {"docs/map/OVERVIEW.md"}

CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs",
    ".java", ".kt", ".swift", ".php", ".cs", ".vue", ".svelte", ".sql", ".sh",
}

FRAMEWORK_PATHS_FILE = ".claude/framework-paths.json"


def framework_owned():
    """Paths belonging to Trellis rather than the project. Single source of truth."""
    try:
        with open(os.path.join(REPO_ROOT, FRAMEWORK_PATHS_FILE)) as fh:
            return [p.rstrip("/") for p in json.load(fh).get("owned", [])]
    except Exception:
        return [".claude", ".githooks", "stacks", "setup"]


def is_framework(rel_path, owned):
    return any(rel_path == o or rel_path.startswith(o + "/") for o in owned)


MANIFESTS = [
    ("package.json", "node"), ("pyproject.toml", "python"), ("requirements.txt", "python"),
    ("go.mod", "go"), ("Cargo.toml", "rust"), ("Gemfile", "ruby"), ("composer.json", "php"),
]


def git(*args, default=""):
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else default
    except Exception:
        return default


def tracked_files():
    """Prefer git — it respects .gitignore for free. Fall back to a walk."""
    listing = git("ls-files")
    if listing:
        return sorted(p for p in listing.splitlines() if p and p not in SELF_EXCLUDE)
    found = []
    for root, dirs, files in os.walk(REPO_ROOT):
        # Skip only what SKIP_DIRS names. A blanket dot-directory skip would hide .claude,
        # which is the most important directory in a Trellis project.
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name == ".DS_Store":
                continue
            rel = os.path.relpath(os.path.join(root, name), REPO_ROOT)
            if rel in SELF_EXCLUDE:
                continue
            if not any(part in SKIP_DIRS for part in rel.split(os.sep)):
                found.append(rel)
    return sorted(found)


def load_json(path):
    try:
        with open(os.path.join(REPO_ROOT, path)) as fh:
            return json.load(fh)
    except Exception:
        return {}




def directory_purpose(rel_dir):
    """A directory can describe itself with a PURPOSE file or a README's first line.

    This is the only way the map carries meaning rather than just structure, and it is the thing worth
    maintaining by hand.
    """
    for name in ("PURPOSE", "PURPOSE.md", "README.md"):
        path = os.path.join(REPO_ROOT, rel_dir, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path) as fh:
                for raw in fh:
                    line = raw.strip()
                    if line and not line.startswith("#"):
                        return line[:160]
        except Exception:
            pass
    return ""


def group_by_area(files):
    """Group by top-level directory — the coarsest grouping that is still informative."""
    areas = {}
    for path in files:
        parts = path.split("/")
        area = parts[0] if len(parts) > 1 else "(root)"
        if area in SKIP_DIRS:
            continue
        areas.setdefault(area, []).append(path)
    return areas


def spec_index():
    specs_dir = os.path.join(REPO_ROOT, "docs", "specs")
    if not os.path.isdir(specs_dir):
        return []
    rows = []
    for name in sorted(os.listdir(specs_dir)):
        if not name.endswith(".md") or name.startswith("_"):
            continue
        meta = parse_file(os.path.join(specs_dir, name))
        rows.append((meta.get("id", name), meta.get("title", ""), meta.get("status", "?"),
                     "docs/specs/" + name))
    return rows


def stack_extractors(config):
    """Stack modules may contribute an extractor that adds a language-aware section."""
    sections = []
    for stack in config.get("stacks", []) or []:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", stack or ""):
            continue
        extractor = os.path.join(REPO_ROOT, "stacks", stack, "extract-map.py")
        if not os.path.exists(extractor):
            continue
        try:
            out = subprocess.run([sys.executable, extractor], cwd=REPO_ROOT,
                                 capture_output=True, text=True, timeout=60)
            if out.returncode == 0 and out.stdout.strip():
                sections.append((stack, out.stdout.strip()))
        except Exception:
            pass
    return sections


def build():
    config = load_json("trellis.json")
    all_files = tracked_files()
    owned = framework_owned()

    # The map exists to describe YOUR project. Trellis ships ~60 of its own files; counting them makes
    # the map mostly about the framework, which is the opposite of saving anyone a read.
    files = [f for f in all_files if not is_framework(f, owned)]
    framework_count = len(all_files) - len(files)
    code = [f for f in files if os.path.splitext(f)[1] in CODE_EXTENSIONS]
    areas = group_by_area(files)

    out = []
    out.append("# Map")
    out.append("")
    out.append("<!-- GENERATED by .claude/scripts/build-map.py — do not edit by hand.")
    out.append("     Directory descriptions come from each directory's PURPOSE or README. Edit those. -->")
    out.append("")

    if config:
        out.append("**{}** — {}".format(config.get("name", "?"), config.get("description", "")))
        out.append("")
        out.append("Type `{}` · stacks: {}".format(
            config.get("type", "?"),
            ", ".join(f"`{s}`" for s in (config.get("stacks") or [])) or "none",
        ))
    else:
        out.append("_No `trellis.json` — the project is not set up yet._")
    out.append("")
    out.append("%d project files, %d of them code." % (len(files), len(code)))
    if framework_count:
        out.append("")
        out.append("_%d framework files (Trellis itself) are excluded — see `.claude/framework-paths.json`._"
                   % framework_count)
    out.append("")

    # ---- where things live -------------------------------------------------
    out.append("## Where things live")
    out.append("")
    out.append("| Area | Files | What it is |")
    out.append("|---|---:|---|")
    for area in sorted(areas):
        purpose = directory_purpose(area) if area != "(root)" else "Top-level config and docs"
        out.append("| `%s` | %d | %s |" % (area, len(areas[area]), purpose or "—"))
    out.append("")
    missing = [a for a in sorted(areas) if a != "(root)" and not directory_purpose(a)]
    if missing:
        out.append("> Undescribed: {}. Add a `PURPOSE` file to each so this map means something."
                   .format(", ".join(f"`{m}`" for m in missing)))
        out.append("")

    # ---- specs -------------------------------------------------------------
    specs = spec_index()
    if specs:
        done = sum(1 for s in specs if s[2] == "done")
        out.append("## Specs")
        out.append("")
        out.append("%d total, %d done." % (len(specs), done))
        out.append("")
        out.append("| Spec | Title | Status |")
        out.append("|---|---|---|")
        for sid, title, status, path in specs:
            out.append(f"| [{sid}](/{path}) | {title} | {status} |")
        out.append("")

    # ---- dependencies ------------------------------------------------------
    for manifest, kind in MANIFESTS:
        if not os.path.exists(os.path.join(REPO_ROOT, manifest)):
            continue
        out.append("## Dependencies")
        out.append("")
        if kind == "node":
            pkg = load_json(manifest)
            runtime = sorted((pkg.get("dependencies") or {}).keys())
            dev = sorted((pkg.get("devDependencies") or {}).keys())
            out.append("From `%s` — %d runtime, %d dev." % (manifest, len(runtime), len(dev)))
            if runtime:
                out.append("")
                out.append("Runtime: {}".format(", ".join(f"`{d}`" for d in runtime)))
        else:
            out.append(f"Declared in `{manifest}`.")
        out.append("")
        break

    # ---- stack-contributed sections ---------------------------------------
    for stack, section in stack_extractors(config):
        out.append(f"## {stack}")
        out.append("")
        out.append(section)
        out.append("")

    # ---- hot spots ---------------------------------------------------------
    churn = git("log", "--since=30.days", "--name-only", "--pretty=format:")
    if churn:
        counts = {}
        for raw in churn.splitlines():
            path = raw.strip()
            if path and os.path.splitext(path)[1] in CODE_EXTENSIONS:
                counts[path] = counts.get(path, 0) + 1
        hot = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
        if hot:
            out.append("## Changing most")
            out.append("")
            out.append("Last 30 days. Where the work is, and where regressions are most likely.")
            out.append("")
            for path, count in hot:
                out.append("- `%s` (%d commits)" % (path, count))
            out.append("")

    out.append("---")
    out.append("")
    out.append("Generated {} from commit `{}`."
               .format(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                  git("rev-parse", "--short", "HEAD", default="none")))
    out.append("")
    out.append("If this disagrees with the code, the code is right — regenerate with "
               "`.claude/scripts/build-map.py`.")

    return "\n".join(out) + "\n"


def content_signature(text):
    """Everything except the generated-at line, so --check does not trip on the timestamp alone."""
    stable = [line for line in text.splitlines() if not line.startswith("Generated ")]
    return hashlib.sha256("\n".join(stable).encode()).hexdigest()


def main():
    fresh = build()

    if "--check" in sys.argv:
        try:
            with open(MAP_FILE) as fh:
                existing = fh.read()
        except Exception:
            print("map: docs/map/OVERVIEW.md is missing. Run .claude/scripts/build-map.py")
            return 1
        if content_signature(existing) != content_signature(fresh):
            print("map: docs/map/OVERVIEW.md is out of date. Run .claude/scripts/build-map.py")
            return 1
        print("map: up to date")
        return 0

    os.makedirs(MAP_DIR, exist_ok=True)
    with open(MAP_FILE, "w") as fh:
        fh.write(fresh)
    print("map: wrote docs/map/OVERVIEW.md (%d lines)" % len(fresh.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
