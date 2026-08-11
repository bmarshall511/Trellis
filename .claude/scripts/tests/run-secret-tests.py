#!/usr/bin/env python3
"""Regression tests for the Trellis secret scanner."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCANNER = os.path.join(HERE, "..", "scan-secrets.py")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
cases = json.load(open(os.path.join(HERE, "secret-cases.json")))
failures = []
for expected, key in ((1, "detect"), (0, "clean")):
    for case in cases[key]:
        # A case may name the file it lives in: some rules depend on the filename, such as the
        # lockfile exemption from the entropy heuristic.
        name, line, filename = (case + [None])[:3] if len(case) < 3 else case
        if filename:
            path = os.path.join(ROOT, filename)
            existed = os.path.exists(path)
            backup = path + ".bak" if existed else None
            if existed:
                os.rename(path, backup)
            with open(path, "w") as fh:
                fh.write(line + "\n")
        else:
            fd, path = tempfile.mkstemp(suffix=".txt", dir=ROOT)
            with os.fdopen(fd, "w") as fh:
                fh.write(line + "\n")
            backup = None
        rel = os.path.relpath(path, ROOT)
        try:
            result = subprocess.run([SCANNER, rel], cwd=ROOT, capture_output=True, text=True)
            if result.returncode != expected:
                failures.append("%s: %s (exit %d, wanted %d)" % (key, name, result.returncode, expected))
        finally:
            os.remove(path)
            if backup:
                os.rename(backup, path)
total = len(cases["detect"]) + len(cases["clean"])
if failures:
    print("FAILING (%d/%d):" % (len(failures), total))
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("secrets: all %d cases pass (%d detected, %d clean)"
      % (total, len(cases["detect"]), len(cases["clean"])))
