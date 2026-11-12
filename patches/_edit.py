"""Tiny helper for drift-tolerant source edits against Mesa.

Usage inside a patch script (run with the Mesa checkout as the current dir):

    from _edit import Edits
    ed = Edits()
    ed.replace("src/freedreno/vulkan/foo.cc", OLD, NEW, "what this edit does")
    ed.commit()

Every anchor (OLD) must appear exactly once. Nothing is written unless ALL
edits in the script match, so a script is either fully applied or not at all.
Exit code 2 means "an anchor no longer matches current Mesa".
"""
import os
import sys


class Edits:
    def __init__(self):
        self._files = {}
        self._log = []

    def _load(self, path):
        if path not in self._files:
            with open(path, encoding="utf-8") as f:
                self._files[path] = f.read()
        return self._files[path]

    def replace(self, path, old, new, label):
        try:
            src = self._load(path)
        except FileNotFoundError:
            self._fail(f"{path}: file not found ({label})")
        n = src.count(old)
        if n != 1:
            self._fail(
                f"{path}: anchor for '{label}' matched {n} times (expected 1). "
                f"Upstream Mesa probably changed this code; update the patch script."
            )
        self._files[path] = src.replace(old, new, 1)
        self._log.append(label)

    def commit(self):
        for path, src in self._files.items():
            with open(path, "w", encoding="utf-8") as f:
                f.write(src)
        for label in self._log:
            print(f"   ok: {label}")

    @staticmethod
    def _fail(msg):
        print(f"!! {msg}", file=sys.stderr)
        sys.exit(2)


def env_int(name, default, lo, hi):
    """Read an integer tuning value from the environment (set by config.env)."""
    try:
        v = int(os.environ.get(name, default))
    except ValueError:
        v = default
    return max(lo, min(hi, v))
