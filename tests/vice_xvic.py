#!/usr/bin/env python3
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOAD_ADDR = 0x1001
START_ADDR = 0x100D


def tool(name):
    return shutil.which(name)


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, **kwargs)


def require_tools():
    missing = [name for name in ("xvic", "xa") if tool(name) is None]
    if missing:
        print(f"SKIP: missing {' '.join(missing)}")
        return False
    return True


def compile_prg(tmp, name, source):
    src = tmp / f"{name}.c"
    asm = tmp / f"{name}.s"
    raw = tmp / f"{name}.raw"
    prg = tmp / f"{name}.prg"
    src.write_text(source)

    proc = run([sys.executable, "smallc.py", str(src), "-o", str(asm)])
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)

    proc = run(["xa", str(asm), "-o", str(raw)])
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)

    prg.write_bytes(LOAD_ADDR.to_bytes(2, "little") + raw.read_bytes())
    return prg


def run_xvic(tmp, prg, watch_addr, expected_a):
    mon = tmp / "commands.mon"
    log = tmp / "monitor.log"
    mon.write_text(
        "\n".join(
            [
                f'load "{prg}" 0',
                f"watch store ${watch_addr:04x} if A == ${expected_a:02x}",
                'command 1 "q"',
                f"goto ${START_ADDR:04x}",
                "",
            ]
        )
    )

    cmd = [
        "xvic",
        "-silent",
        "-sounddev",
        "dummy",
        "-warp",
        "-monlog",
        "-monlogname",
        str(log),
        "-moncommands",
        str(mon),
        "-limitcycles",
        "1000000",
    ]
    if tool("xvfb-run"):
        cmd = ["xvfb-run", "-a", *cmd]

    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=15)
    log_text = log.read_text() if log.exists() else ""
    if proc.returncode != 0:
        raise AssertionError(
            f"xvic failed with {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}\nlog:\n{log_text}"
        )
    if "Executing: q" not in log_text or f"A:{expected_a:02X}" not in log_text:
        raise AssertionError(f"watchpoint did not observe A=${expected_a:02x}\n{log_text}")
    return log_text


def main():
    if not require_tools():
        return 0

    cases = [
        (
            "poke_literal",
            """
            int main() {
              poke(7680, 42);
              while (1) {}
              return 0;
            }
            """,
            0x1E00,
            42,
        ),
        (
            "loop_arithmetic",
            """
            int i;
            int total;

            int main() {
              i = 0;
              total = 1;
              while (i < 4) {
                total = total + 3;
                i = i + 1;
              }
              if (total == 13) {
                poke(7681, total);
              } else {
                poke(7681, 99);
              }
              while (1) {}
              return 0;
            }
            """,
            0x1E01,
            13,
        ),
    ]

    with tempfile.TemporaryDirectory(prefix="smallc-vice-") as td:
        tmp = Path(td)
        for name, source, watch_addr, expected_a in cases:
            prg = compile_prg(tmp, name, source)
            run_xvic(tmp, prg, watch_addr, expected_a)
            print(f"PASS: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
