# smallc

`smallc` is a tiny compiler that translates a small C subset into 6502 assembly.

The project is aimed at experimentation and learning:

- Parsing and lowering a compact C-like language.
- Emitting runnable assembly for the VIC-20 memory layout.
- Keeping the compiler implementation in a single, readable Python file.

## What it supports

### Source language (subset C)

- Global variables: `int name;`
- Functions: `int name() { ... }` (no parameters)
- Statements:
 	- expression statements
 	- `return expr;`
 	- `if (...) stmt [else stmt]`
 	- `while (...) stmt`
 	- block statements `{ ... }`
- Expressions:
 	- integer literals (`123`, `0x7b`)
 	- variable reads/writes
 	- unary minus (`-x`)
 	- binary arithmetic: `+ - * / %`
 	- comparisons: `== != < <= > >=`
 	- assignment: `x = expr`
 	- function calls

### Built-in functions

- `putc(value)` -> writes low byte through KERNAL `CHROUT` (`$ffd2`)
- `poke(addr, value)` -> stores low byte at memory address
- `peek(addr)` -> reads byte from memory address (returns 16-bit value)

### Codegen/runtime notes

- Values are 16-bit.
- Global variables are emitted as `.word`.
- Runtime helper routines are emitted into the output assembly (`__add16`, `__sub16`, `__mul16`, comparisons, etc.).
- Compilation requires an `int main()` function.

## Targets

- `vic20` (default): emits BASIC loader header and start sequence at `$1001`.
- `plain6502`: emits a plain `__start` entry with no VIC-20 BASIC stub.

## Quick start

Requirements:

- Python 3

Compile an example to stdout:

```bash
python3 smallc.py examples/hello.c
```

Write assembly to a file:

```bash
python3 smallc.py examples/hello.c -o build/hello.s
```

Use plain 6502 output:

```bash
python3 smallc.py examples/hello.c --target plain6502 -o build/hello.s
```

Compile from stdin:

```bash
echo 'int main(){ putc(65); return 0; }' | python3 smallc.py -
```

## Examples

- `examples/hello.c`: prints `A`..`E` and carriage return using `putc`.
- `examples/poke.c`: writes a sequence of values into screen color RAM via `poke`.

Generate both example assembly files:

```bash
make examples
```

## Testing

Run all tests:

```bash
make test
```

This runs:

- `tests/smoke.py`: compiler and output-shape checks.
- `tests/vice_xvic.py`: integration checks using assembler + emulator.

Run only emulator integration tests:

```bash
make vice-test
```

### Emulator test prerequisites

`tests/vice_xvic.py` requires:

- `xa` (6502 assembler)
- `xvic` (VICE VIC-20 emulator)

If either tool is missing, the test script prints a skip message and exits successfully.

## Project layout

```text
smallc.py          Compiler (lexer, parser, codegen, CLI)
examples/          Sample subset-C programs
tests/smoke.py     Fast compile/smoke validation
tests/vice_xvic.py VIC-20 integration test using xa + xvic
Makefile           Common commands
```

## Development commands

```bash
make examples   # compile sample inputs to build/*.s
make test       # run smoke + VICE integration tests
make clean      # remove build/
```

## Current limitations

- No local variables or function parameters.
- No type system beyond `int`.
- No pointers, arrays, structs, strings, or preprocessor support.
- Function calls are either built-ins or zero-argument user-defined functions.
- No separate compilation or linker workflow.

## License

This is under the LGPL2.1, see LICENSE in the repo.
