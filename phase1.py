"""
Simple intermediate code generator with 4 main phases:
1. Lexical analysis
2. Syntax analysis + AST construction
3. Intermediate code generation
4. Code optimization (on intermediate code)

The tiny language we support here:

    program   ::= stmt (';' stmt)*
    stmt      ::= IDENT '=' expr | expr
    expr      ::= term (('+' | '-') term)*
    term      ::= factor (('*' | '/') factor)*
    factor    ::= NUMBER | IDENT | '(' expr ')'

Intermediate code is emitted as three‑address instructions, e.g.:

    t1 = 2 * 3
    t2 = 4 + 5
    t3 = t1 + t2
    x = t3

Optimization performs simple constant folding on the generated code.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Union, Tuple


# ========== LEXICAL ANALYZER PHASE ==========

TokenType = str


@dataclass
class Token:
    """One lexical token. line/column are 1-based (set by lex)."""

    type: TokenType
    value: str
    position: int
    line: int = 1
    column: int = 1


# Order matters: longer / comment patterns must come before SLASH ("/").
TOKEN_SPEC = [
    ("NUMBER", r"\d+(\.\d+)?"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    # Block comments /* ... */ (non-greedy so nested-looking text is still skipped as one block)
    ("COMMENT_BLOCK", r"/\*[\s\S]*?\*/"),
    # Line comments // ... until end of line
    ("COMMENT_LINE", r"//[^\n]*"),
    ("SLASH", r"/"),
    ("ASSIGN", r"="),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("SEMI", r";"),
    # Whitespace (spaces, tabs, newlines) — ignored, not emitted as tokens
    ("SKIP", r"[ \t\r\n]+"),
    ("MISMATCH", r"."),
]

MASTER_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))


def position_to_line_col(source: str, pos: int) -> Tuple[int, int]:
    """Map a 0-based index in source to 1-based (line, column)."""
    if pos < 0:
        pos = 0
    if pos > len(source):
        pos = len(source)
    prefix = source[:pos]
    line = 1 + prefix.count("\n")
    last_nl = prefix.rfind("\n")
    if last_nl == -1:
        column = pos + 1
    else:
        column = pos - last_nl
    return line, column


def lex_error(source: str, pos: int, msg: str) -> None:
    """
    Raise SyntaxError with line, column, and position for clear lexer diagnostics.
    Use this for any invalid character or lexer rule violation.
    """
    line, col = position_to_line_col(source, pos)
    raise SyntaxError(
        f"Lexical error at line {line}, column {col} (character position {pos}): {msg}"
    )


def format_tokens_table(tokens: List[Token]) -> str:
    """
    Compact token list: one row per token — index, line, column, type, lexeme (value).
    """
    lines: List[str] = []
    lines.append("PHASE 1 - LEXICAL ANALYZER")
    lines.append("")
    header = f"{'#':>3}  {'Ln':>3}  {'Col':>3}   {'Type':<8}   Lexeme (text)"
    lines.append(header)
    lines.append("-" * 50)

    n = 0
    for t in tokens:
        if t.type == "EOF":
            lines.append(f"{'--':>3}  {'--':>3}  {'--':>3}   {'EOF':<8}   (end of input)")
            break
        n += 1
        lex = t.value.replace("\n", "\\n").replace("\t", "\\t")
        lines.append(f"{n:>3}  {t.line:>3}  {t.column:>3}   {t.type:<8}   {lex}")

    lines.append("")
    lines.append(f"Tokens: {n}")
    return "\n".join(lines)


def show_tokens(tokens: List[Token]) -> None:
    """Print the full formatted token table to stdout."""
    print(format_tokens_table(tokens))


def lex(source: str) -> List[Token]:
    """
    Convert input string into a list of tokens.

    - Extra spaces and line breaks are skipped (not tokenized).
    - // line comments and /* block comments */ are skipped.
    - Each token carries line/column of its first character (for errors and display).
    """
    tokens: List[Token] = []
    for match in MASTER_REGEX.finditer(source):
        kind = match.lastgroup
        value = match.group()
        pos = match.start()
        line, column = position_to_line_col(source, pos)

        if kind == "SKIP":
            continue
        if kind in ("COMMENT_LINE", "COMMENT_BLOCK"):
            continue
        if kind == "MISMATCH":
            lex_error(source, pos, f"unexpected character {value!r}")

        tokens.append(Token(kind, value, pos, line, column))

    end_pos = len(source)
    el, ec = position_to_line_col(source, end_pos)
    tokens.append(Token("EOF", "", end_pos, el, ec))
    return tokens


# ========== AST NODES (SYNTAX + AST PHASE) ==========


@dataclass
class ASTNode:
    pass


@dataclass
class Number(ASTNode):
    value: Union[int, float]


@dataclass
class Variable(ASTNode):
    name: str


@dataclass
class BinaryOp(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class Assign(ASTNode):
    name: str
    expr: ASTNode


@dataclass
class Program(ASTNode):
    statements: List[ASTNode]


class Parser:
    """Recursive‑descent parser building the AST from tokens."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.current
        self.pos += 1
        return tok

    def expect(self, token_type: TokenType) -> Token:
        if self.current.type != token_type:
            t = self.current
            raise SyntaxError(
                f"Expected token {token_type}, got {t.type} at line {t.line}, column {t.column} "
                f"(position {t.position})"
            )
        return self.advance()

    def parse(self) -> Program:
        statements: List[ASTNode] = []
        while self.current.type != "EOF":
            statements.append(self.statement())
            if self.current.type == "SEMI":
                self.advance()
            else:
                break
        return Program(statements)

    def statement(self) -> ASTNode:
        if self.current.type == "IDENT" and self._peek().type == "ASSIGN":
            name = self.advance().value
            self.expect("ASSIGN")
            expr = self.expr()
            return Assign(name, expr)
        return self.expr()

    def expr(self) -> ASTNode:
        node = self.term()
        while self.current.type in ("PLUS", "MINUS"):
            op_token = self.advance()
            right = self.term()
            node = BinaryOp(op_token.type, node, right)
        return node

    def term(self) -> ASTNode:
        node = self.factor()
        while self.current.type in ("STAR", "SLASH"):
            op_token = self.advance()
            right = self.factor()
            node = BinaryOp(op_token.type, node, right)
        return node

    def factor(self) -> ASTNode:
        tok = self.current
        if tok.type == "NUMBER":
            self.advance()
            value = float(tok.value) if "." in tok.value else int(tok.value)
            return Number(value)
        if tok.type == "IDENT":
            self.advance()
            return Variable(tok.value)
        if tok.type == "LPAREN":
            self.advance()
            node = self.expr()
            self.expect("RPAREN")
            return node
        raise SyntaxError(
            f"Unexpected token {tok.type} at line {tok.line}, column {tok.column} (position {tok.position})"
        )

    def _peek(self) -> Token:
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        return self.tokens[-1]


# ========== INTERMEDIATE CODE GENERATION PHASE ==========


@dataclass
class Instruction:
    target: str
    op: str
    arg1: Optional[str] = None
    arg2: Optional[str] = None

    def __str__(self) -> str:
        if self.op == "MOV":
            return f"{self.target} = {self.arg1}"
        if self.op in ("+", "-", "*", "/"):
            return f"{self.target} = {self.arg1} {self.op} {self.arg2}"
        if self.op == "CONST":
            return f"{self.target} = {self.arg1}"
        return f"{self.target}: {self.op} {self.arg1 or ''} {self.arg2 or ''}".strip()


class CodeGenerator:
    """Generate three‑address code from the AST."""

    def __init__(self):
        self.temp_counter = 0
        self.instructions: List[Instruction] = []

    def new_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def generate(self, node: ASTNode) -> Tuple[List[Instruction], List[str]]:
        """Return list of instructions and list of result variables (for each top‑level stmt)."""
        self.temp_counter = 0
        self.instructions = []
        results: List[str] = []

        if isinstance(node, Program):
            for stmt in node.statements:
                res = self._gen_node(stmt)
                if res is not None:
                    results.append(res)
        else:
            res = self._gen_node(node)
            if res is not None:
                results.append(res)

        return self.instructions, results

    def _gen_node(self, node: ASTNode) -> Optional[str]:
        if isinstance(node, Number):
            temp = self.new_temp()
            self.instructions.append(Instruction(temp, "CONST", str(node.value)))
            return temp

        if isinstance(node, Variable):
            return node.name

        if isinstance(node, BinaryOp):
            left = self._gen_node(node.left)
            right = self._gen_node(node.right)
            temp = self.new_temp()
            op_map = {
                "PLUS": "+",
                "MINUS": "-",
                "STAR": "*",
                "SLASH": "/",
            }
            op_symbol = op_map[node.op]
            self.instructions.append(Instruction(temp, op_symbol, left, right))
            return temp

        if isinstance(node, Assign):
            src = self._gen_node(node.expr)
            self.instructions.append(Instruction(node.name, "MOV", src))
            return node.name

        if isinstance(node, Program):
            # handled in generate()
            return None

        raise TypeError(f"Unsupported AST node: {type(node).__name__}")


# ========== SIMPLE CODE OPTIMIZATION PHASE ==========


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _eval_op(op: str, a: float, b: float) -> float:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b
    raise ValueError(f"Unknown op {op}")


def optimize_instructions(instructions: List[Instruction]) -> List[Instruction]:
    """
    Perform simple constant folding on three‑address code:
    - t = CONST a, u = CONST b, v = t + u  ==>  v = CONST (a+b)
    - t = CONST a, x = MOV t               ==>  x = CONST a
    """
    const_values: dict[str, float] = {}
    optimized: List[Instruction] = []

    for instr in instructions:
        if instr.op == "CONST" and instr.arg1 is not None and _is_number(instr.arg1):
            const_values[instr.target] = float(instr.arg1)
            optimized.append(instr)
        elif instr.op in ("+", "-", "*", "/"):
            a = instr.arg1
            b = instr.arg2
            a_val = const_values.get(a) if a is not None else None
            b_val = const_values.get(b) if b is not None else None

            if a is not None and b is not None and (
                (_is_number(a) and _is_number(b))
                or (a_val is not None and _is_number(b))
                or (_is_number(a) and b_val is not None)
                or (a_val is not None and b_val is not None)
            ):
                # Resolve raw numbers or temps into concrete numbers
                a_num = float(a) if _is_number(a) else const_values[a]
                b_num = float(b) if _is_number(b) else const_values[b]
                result = _eval_op(instr.op, a_num, b_num)
                const_values[instr.target] = result
                optimized.append(Instruction(instr.target, "CONST", str(result)))
            else:
                optimized.append(instr)
        elif instr.op == "MOV":
            src = instr.arg1
            if src in const_values:
                val = const_values[src]
                const_values[instr.target] = val
                optimized.append(Instruction(instr.target, "CONST", str(val)))
            else:
                optimized.append(instr)
        else:
            optimized.append(instr)

    return optimized


# ========== PUBLIC API / DRIVER ==========


def format_tokens(tokens: List[Token]) -> str:
    """Return a clear, multi-line token table (same as format_tokens_table) for UI display."""
    return format_tokens_table(tokens)


def format_ast(node: ASTNode) -> str:
    """Return a simple one-line representation of the AST (for UI display)."""

    def _inner(n: ASTNode) -> str:
        if isinstance(n, Number):
            return str(n.value)
        if isinstance(n, Variable):
            return n.name
        if isinstance(n, BinaryOp):
            return f"({ _inner(n.left) } { n.op } { _inner(n.right) })"
        if isinstance(n, Assign):
            return f"{n.name} = {_inner(n.expr)}"
        if isinstance(n, Program):
            return "; ".join(_inner(s) for s in n.statements)
        return f"<{type(n).__name__}>"

    return _inner(node)


def format_instructions(instructions: List[Instruction]) -> str:
    """Return multi-line formatted three-address code as a single string."""
    return "\n".join(str(instr) for instr in instructions)


def compile_source(source: str) -> Tuple[List[Instruction], List[Instruction]]:
    """
    Convenience function that runs all phases:
    1) lex  2) parse + AST  3) codegen  4) optimization
    Returns (raw_instructions, optimized_instructions).
    """
    tokens = lex(source)
    parser = Parser(tokens)
    ast = parser.parse()
    codegen = CodeGenerator()
    raw_instructions, _ = codegen.generate(ast)
    optimized_instructions = optimize_instructions(raw_instructions)
    return raw_instructions, optimized_instructions


def main() -> None:
    # Example usage; you can modify or remove this.
    source = input("Enter expression or assignments (e.g. 'x = 2*3 + 4; y = x + 5'): ")
    raw, optimized = compile_source(source)

    print("\n=== Raw three‑address code ===")
    for instr in raw:
        print(str(instr))

    print("\n=== Optimized three‑address code ===")
    for instr in optimized:
        print(str(instr))


if __name__ == "__main__":
    main()