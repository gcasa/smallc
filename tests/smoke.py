#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def assert_contains(text, needle):
    if needle not in text:
        print(text)
        raise AssertionError(f"missing {needle!r}")


def main():
    hello = run([sys.executable, "smallc.py", "examples/hello.c"])
    if hello.returncode != 0:
        print(hello.stderr)
        return hello.returncode
    assert_contains(hello.stdout, "jsr _main")
    assert_contains(hello.stdout, "__mul16:")
    assert_contains(hello.stdout, "jsr $ffd2")
    assert_contains(hello.stdout, "_i:")

    bad = run([sys.executable, "smallc.py", "-"])
    if bad.returncode == 0:
        print("expected stdin compile to fail on empty input")
        return 1

    src = "int x; int main(){ x = 3; if (x >= 2) putc(88); else putc(89); return x; }"
    proc = subprocess.run(
        [sys.executable, "smallc.py", "-", "--target", "plain6502"],
        cwd=ROOT,
        input=src,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(proc.stderr)
        return proc.returncode
    assert_contains(proc.stdout, "_main:")
    assert_contains(proc.stdout, "__cmp_ge")
    assert_contains(proc.stdout, "rts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
