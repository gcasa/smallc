#!/usr/bin/env python3
"""A tiny subset-C to 6502 assembly compiler."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


KEYWORDS = {"int", "return", "if", "else", "while"}
TOKEN_RE = re.compile(
    r"""
    (?P<WS>[ \t\r\n]+)
  | (?P<LINE>//[^\n]*)
  | (?P<BLOCK>/\*.*?\*/)
  | (?P<NUM>0x[0-9a-fA-F]+|\d+)
  | (?P<ID>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP>==|!=|<=|>=|[+\-*/%<>=;(),{}])
  | (?P<MISMATCH>.)
    """,
    re.S | re.X,
)


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    col: int


class CompileError(Exception):
    pass


def lex(source: str) -> list[Token]:
    out: list[Token] = []
    line = 1
    line_start = 0
    for match in TOKEN_RE.finditer(source):
        kind = match.lastgroup or "MISMATCH"
        text = match.group()
        col = match.start() - line_start + 1
        if kind in {"WS", "LINE", "BLOCK"}:
            pass
        elif kind == "ID" and text in KEYWORDS:
            out.append(Token(text, text, line, col))
        elif kind == "ID":
            out.append(Token("ID", text, line, col))
        elif kind == "NUM":
            out.append(Token("NUM", text, line, col))
        elif kind == "OP":
            out.append(Token(text, text, line, col))
        else:
            raise CompileError(f"{line}:{col}: unexpected character {text!r}")
        line += text.count("\n")
        if "\n" in text:
            line_start = match.start() + text.rfind("\n") + 1
    out.append(Token("EOF", "", line, 1))
    return out


@dataclass
class Program:
    globals: list[str]
    functions: list["Function"]


@dataclass
class Function:
    name: str
    body: list["Stmt"]


class Stmt:
    pass


@dataclass
class Block(Stmt):
    body: list[Stmt]


@dataclass
class Return(Stmt):
    value: "Expr"


@dataclass
class If(Stmt):
    cond: "Expr"
    then: Stmt
    otherwise: Stmt | None


@dataclass
class While(Stmt):
    cond: "Expr"
    body: Stmt


@dataclass
class ExprStmt(Stmt):
    expr: "Expr"


class Expr:
    pass


@dataclass
class Num(Expr):
    value: int


@dataclass
class Var(Expr):
    name: str


@dataclass
class Assign(Expr):
    name: str
    value: Expr


@dataclass
class Unary(Expr):
    op: str
    expr: Expr


@dataclass
class Binary(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class Call(Expr):
    name: str
    args: list[Expr]


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def cur(self) -> Token:
        return self.tokens[self.i]

    def match(self, *kinds: str) -> Token | None:
        if self.cur().kind in kinds:
            tok = self.cur()
            self.i += 1
            return tok
        return None

    def expect(self, kind: str) -> Token:
        tok = self.match(kind)
        if tok is None:
            got = self.cur()
            raise CompileError(f"{got.line}:{got.col}: expected {kind}, got {got.value or got.kind}")
        return tok

    def parse(self) -> Program:
        globals_: list[str] = []
        functions: list[Function] = []
        while self.cur().kind != "EOF":
            self.expect("int")
            name = self.expect("ID").value
            if self.match(";"):
                globals_.append(name)
            else:
                self.expect("(")
                self.expect(")")
                functions.append(Function(name, self.block_body()))
        if not functions:
            raise CompileError("no functions found")
        return Program(globals_, functions)

    def block_body(self) -> list[Stmt]:
        self.expect("{")
        body: list[Stmt] = []
        while not self.match("}"):
            if self.cur().kind == "EOF":
                raise CompileError("unexpected end of file in block")
            body.append(self.statement())
        return body

    def statement(self) -> Stmt:
        if self.cur().kind == "{":
            return Block(self.block_body())
        if self.match("return"):
            value = self.expr()
            self.expect(";")
            return Return(value)
        if self.match("if"):
            self.expect("(")
            cond = self.expr()
            self.expect(")")
            then = self.statement()
            otherwise = self.statement() if self.match("else") else None
            return If(cond, then, otherwise)
        if self.match("while"):
            self.expect("(")
            cond = self.expr()
            self.expect(")")
            return While(cond, self.statement())
        expr = self.expr()
        self.expect(";")
        return ExprStmt(expr)

    def expr(self) -> Expr:
        return self.assignment()

    def assignment(self) -> Expr:
        left = self.equality()
        if self.match("="):
            if not isinstance(left, Var):
                tok = self.cur()
                raise CompileError(f"{tok.line}:{tok.col}: assignment target must be a variable")
            return Assign(left.name, self.assignment())
        return left

    def equality(self) -> Expr:
        expr = self.relation()
        while (op := self.match("==", "!=")) is not None:
            expr = Binary(op.kind, expr, self.relation())
        return expr

    def relation(self) -> Expr:
        expr = self.add()
        while (op := self.match("<", "<=", ">", ">=")) is not None:
            expr = Binary(op.kind, expr, self.add())
        return expr

    def add(self) -> Expr:
        expr = self.mul()
        while (op := self.match("+", "-")) is not None:
            expr = Binary(op.kind, expr, self.mul())
        return expr

    def mul(self) -> Expr:
        expr = self.unary()
        while (op := self.match("*", "/", "%")) is not None:
            expr = Binary(op.kind, expr, self.unary())
        return expr

    def unary(self) -> Expr:
        if self.match("-"):
            return Unary("-", self.unary())
        return self.primary()

    def primary(self) -> Expr:
        if tok := self.match("NUM"):
            return Num(int(tok.value, 0) & 0xFFFF)
        if tok := self.match("ID"):
            name = tok.value
            if self.match("("):
                args: list[Expr] = []
                if not self.match(")"):
                    args.append(self.expr())
                    while self.match(","):
                        args.append(self.expr())
                    self.expect(")")
                return Call(name, args)
            return Var(name)
        if self.match("("):
            expr = self.expr()
            self.expect(")")
            return expr
        tok = self.cur()
        raise CompileError(f"{tok.line}:{tok.col}: expected expression")


class Codegen:
    def __init__(self, program: Program, target: str):
        self.program = program
        self.target = target
        self.lines: list[str] = []
        self.label_id = 0
        self.globals = set(program.globals)
        self.functions = {fn.name for fn in program.functions}
        self.return_label = ""

    def emit(self, line: str = "") -> None:
        self.lines.append(line)

    def label(self, prefix: str) -> str:
        self.label_id += 1
        return f"__{prefix}_{self.label_id}"

    def compile(self) -> str:
        if "main" not in self.functions:
            raise CompileError("missing int main()")
        self.header()
        for fn in self.program.functions:
            self.function(fn)
        self.runtime()
        self.data()
        return "\n".join(self.lines) + "\n"

    def header(self) -> None:
        self.emit("; generated by smallc.py")
        self.emit("; r0=$fb/$fc, r1=$fd/$fe")
        if self.target == "vic20":
            self.emit("* = $1001")
            self.emit(".word __basic_next")
            self.emit(".word 10")
            self.emit(".byte $9e")
            self.emit(".byte \"4109\",0")
            self.emit("__basic_next:")
            self.emit(".word 0")
            self.emit("__start:")
            self.emit("  jsr _main")
            self.emit("  rts")
        else:
            self.emit("__start:")
            self.emit("  jsr _main")
            self.emit("  rts")
        self.emit()

    def function(self, fn: Function) -> None:
        self.return_label = self.label(f"{fn.name}_return")
        self.emit(f"_{fn.name}:")
        for stmt in fn.body:
            self.stmt(stmt)
        self.load_const(0)
        self.emit(f"{self.return_label}:")
        self.emit("  rts")
        self.emit()

    def stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, Block):
            for item in stmt.body:
                self.stmt(item)
        elif isinstance(stmt, Return):
            self.expr(stmt.value)
            self.emit(f"  jmp {self.return_label}")
        elif isinstance(stmt, If):
            else_label = self.label("else")
            end_label = self.label("endif")
            self.expr(stmt.cond)
            self.branch_false(else_label)
            self.stmt(stmt.then)
            self.emit(f"  jmp {end_label}")
            self.emit(f"{else_label}:")
            if stmt.otherwise:
                self.stmt(stmt.otherwise)
            self.emit(f"{end_label}:")
        elif isinstance(stmt, While):
            start = self.label("while")
            end = self.label("endwhile")
            self.emit(f"{start}:")
            self.expr(stmt.cond)
            self.branch_false(end)
            self.stmt(stmt.body)
            self.emit(f"  jmp {start}")
            self.emit(f"{end}:")
        elif isinstance(stmt, ExprStmt):
            self.expr(stmt.expr)
        else:
            raise AssertionError(stmt)

    def expr(self, expr: Expr) -> None:
        if isinstance(expr, Num):
            self.load_const(expr.value)
        elif isinstance(expr, Var):
            self.require_global(expr.name)
            self.emit(f"  lda _{expr.name}")
            self.emit("  sta $fb")
            self.emit(f"  lda _{expr.name}+1")
            self.emit("  sta $fc")
        elif isinstance(expr, Assign):
            self.require_global(expr.name)
            self.expr(expr.value)
            self.emit("  lda $fb")
            self.emit(f"  sta _{expr.name}")
            self.emit("  lda $fc")
            self.emit(f"  sta _{expr.name}+1")
        elif isinstance(expr, Unary):
            self.expr(expr.expr)
            self.emit("  jsr __neg16")
        elif isinstance(expr, Binary):
            self.expr(expr.left)
            self.push_r0()
            self.expr(expr.right)
            self.pop_r1()
            helper = {
                "+": "__add16",
                "-": "__sub16",
                "*": "__mul16",
                "/": "__div16",
                "%": "__mod16",
                "==": "__cmp_eq",
                "!=": "__cmp_ne",
                "<": "__cmp_lt",
                "<=": "__cmp_le",
                ">": "__cmp_gt",
                ">=": "__cmp_ge",
            }[expr.op]
            self.emit(f"  jsr {helper}")
        elif isinstance(expr, Call):
            self.call(expr)
        else:
            raise AssertionError(expr)

    def call(self, call: Call) -> None:
        if call.name == "putc":
            self.arity(call, 1)
            self.expr(call.args[0])
            self.emit("  lda $fb")
            self.emit("  jsr $ffd2")
            self.load_const(0)
        elif call.name == "poke":
            self.arity(call, 2)
            self.expr(call.args[0])
            self.push_r0()
            self.expr(call.args[1])
            self.emit("  lda $fb")
            self.emit("  sta $ff")
            self.pop_r1()
            self.emit("  lda $ff")
            self.emit("  ldy #0")
            self.emit("  sta ($fd),y")
            self.load_const(0)
        elif call.name == "peek":
            self.arity(call, 1)
            self.expr(call.args[0])
            self.emit("  ldy #0")
            self.emit("  lda ($fb),y")
            self.emit("  sta $fb")
            self.emit("  lda #0")
            self.emit("  sta $fc")
        elif call.name in self.functions:
            self.arity(call, 0)
            self.emit(f"  jsr _{call.name}")
        else:
            raise CompileError(f"unknown function {call.name!r}")

    def arity(self, call: Call, expected: int) -> None:
        if len(call.args) != expected:
            raise CompileError(f"{call.name} expects {expected} argument(s)")

    def require_global(self, name: str) -> None:
        if name not in self.globals:
            raise CompileError(f"unknown variable {name!r}")

    def load_const(self, value: int) -> None:
        self.emit(f"  lda #<{value}")
        self.emit("  sta $fb")
        self.emit(f"  lda #>{value}")
        self.emit("  sta $fc")

    def push_r0(self) -> None:
        self.emit("  lda $fc")
        self.emit("  pha")
        self.emit("  lda $fb")
        self.emit("  pha")

    def pop_r1(self) -> None:
        self.emit("  pla")
        self.emit("  sta $fd")
        self.emit("  pla")
        self.emit("  sta $fe")

    def branch_false(self, label: str) -> None:
        self.emit("  lda $fb")
        self.emit("  ora $fc")
        self.emit(f"  beq {label}")

    def runtime(self) -> None:
        self.emit("__add16:")
        self.emit("  clc")
        self.emit("  lda $fd")
        self.emit("  adc $fb")
        self.emit("  sta $fb")
        self.emit("  lda $fe")
        self.emit("  adc $fc")
        self.emit("  sta $fc")
        self.emit("  rts")
        self.emit("__sub16:")
        self.emit("  sec")
        self.emit("  lda $fd")
        self.emit("  sbc $fb")
        self.emit("  sta $fb")
        self.emit("  lda $fe")
        self.emit("  sbc $fc")
        self.emit("  sta $fc")
        self.emit("  rts")
        self.emit("__neg16:")
        self.emit("  sec")
        self.emit("  lda #0")
        self.emit("  sbc $fb")
        self.emit("  sta $fb")
        self.emit("  lda #0")
        self.emit("  sbc $fc")
        self.emit("  sta $fc")
        self.emit("  rts")
        self.emit("__mul16:")
        self.emit("  lda #0")
        self.emit("  sta $ff")
        self.emit("  sta $02")
        self.emit("  ldx #16")
        self.emit("__mul_loop:")
        self.emit("  lsr $fe")
        self.emit("  ror $fd")
        self.emit("  bcc __mul_skip")
        self.emit("  clc")
        self.emit("  lda $ff")
        self.emit("  adc $fb")
        self.emit("  sta $ff")
        self.emit("  lda $02")
        self.emit("  adc $fc")
        self.emit("  sta $02")
        self.emit("__mul_skip:")
        self.emit("  asl $fb")
        self.emit("  rol $fc")
        self.emit("  dex")
        self.emit("  bne __mul_loop")
        self.emit("  lda $ff")
        self.emit("  sta $fb")
        self.emit("  lda $02")
        self.emit("  sta $fc")
        self.emit("  rts")
        self.emit("__div16:")
        self.emit("  jsr __udivmod16")
        self.emit("  rts")
        self.emit("__mod16:")
        self.emit("  jsr __udivmod16")
        self.emit("  lda $ff")
        self.emit("  sta $fb")
        self.emit("  lda $02")
        self.emit("  sta $fc")
        self.emit("  rts")
        self.emit("__udivmod16:")
        self.emit("  lda #0")
        self.emit("  sta $ff")
        self.emit("  sta $02")
        self.emit("  ldx #16")
        self.emit("__div_loop:")
        self.emit("  asl $fd")
        self.emit("  rol $fe")
        self.emit("  rol $ff")
        self.emit("  rol $02")
        self.emit("  sec")
        self.emit("  lda $ff")
        self.emit("  sbc $fb")
        self.emit("  tay")
        self.emit("  lda $02")
        self.emit("  sbc $fc")
        self.emit("  bcc __div_skip")
        self.emit("  sta $02")
        self.emit("  sty $ff")
        self.emit("  inc $fd")
        self.emit("__div_skip:")
        self.emit("  dex")
        self.emit("  bne __div_loop")
        self.emit("  lda $fd")
        self.emit("  sta $fb")
        self.emit("  lda $fe")
        self.emit("  sta $fc")
        self.emit("  rts")
        for name, branch in [
            ("eq", "beq"),
            ("ne", "bne"),
            ("lt", "bcc"),
            ("ge", "bcs"),
        ]:
            self.emit(f"__cmp_{name}:")
            self.emit("  jsr __cmp16")
            self.emit(f"  {branch} __true")
            self.emit("  jmp __false")
        self.emit("__cmp_le:")
        self.emit("  jsr __cmp16")
        self.emit("  beq __true")
        self.emit("  bcc __true")
        self.emit("  jmp __false")
        self.emit("__cmp_gt:")
        self.emit("  jsr __cmp16")
        self.emit("  beq __false")
        self.emit("  bcs __true")
        self.emit("  jmp __false")
        self.emit("__cmp16:")
        self.emit("  lda $fe")
        self.emit("  cmp $fc")
        self.emit("  bne __cmp_done")
        self.emit("  lda $fd")
        self.emit("  cmp $fb")
        self.emit("__cmp_done:")
        self.emit("  rts")
        self.emit("__true:")
        self.load_const(1)
        self.emit("  rts")
        self.emit("__false:")
        self.load_const(0)
        self.emit("  rts")
        self.emit()

    def data(self) -> None:
        if not self.program.globals:
            return
        self.emit("; globals")
        for name in self.program.globals:
            self.emit(f"_{name}: .word 0")


def compile_source(source: str, target: str) -> str:
    return Codegen(Parser(lex(source)).parse(), target).compile()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="compile subset C to tiny 6502 assembly")
    ap.add_argument("input", help="input C file, or - for stdin")
    ap.add_argument("-o", "--output", help="output assembly file")
    ap.add_argument("--target", choices=["vic20", "plain6502"], default="vic20")
    ns = ap.parse_args(argv)

    try:
        source = sys.stdin.read() if ns.input == "-" else Path(ns.input).read_text()
        asm = compile_source(source, ns.target)
    except (OSError, CompileError) as exc:
        print(f"smallc: error: {exc}", file=sys.stderr)
        return 1

    if ns.output:
        out = Path(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(asm)
    else:
        sys.stdout.write(asm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
