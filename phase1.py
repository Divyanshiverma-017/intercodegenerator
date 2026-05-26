"""
Intermediate code generator with a small full-program language.

Supported program elements:
- declaration: int x;  or  int x = expr;
- assignment: x = expr;
- printf: printf(expr);
- if/else: if (cond) { ... } else { ... }
- while: while (cond) { ... }
- blocks: { statement* }

Expressions:
- arithmetic: +, -, *, /
- comparisons: ==, !=, <, <=, >, >=
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

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


KEYWORDS = {
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "printf": "PRINT",
    "int": "INT",
}

# Python keywords that should not be allowed in C code
PYTHON_KEYWORDS = {
    "def", "class", "import", "from", "as", "return", "yield", "raise",
    "except", "finally", "with", "lambda", "pass", "break", "continue",
    "global", "nonlocal", "assert", "async", "await", "del", "in", "is",
    "not", "and", "or", "True", "False", "None"
}

# Order matters: long patterns before short patterns.
TOKEN_SPEC = [
    ("NUMBER", r"\d+(\.\d+)?"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("EQ", r"=="),
    ("NE", r"!="),
    ("LE", r"<="),
    ("GE", r">="),
    ("LT", r"<"),
    ("GT", r">"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("COMMENT_BLOCK", r"/\*[\s\S]*?\*/"),
    ("COMMENT_LINE", r"//[^\n]*"),
    ("SLASH", r"/"),
    ("ASSIGN", r"="),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("SEMI", r";"),
    ("SKIP", r"[ \t\r\n]+"),
    ("MISMATCH", r"."),
]

MASTER_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))


def position_to_line_col(source: str, pos: int) -> Tuple[int, int]:
    if pos < 0:
        pos = 0
    if pos > len(source):
        pos = len(source)
    prefix = source[:pos]
    line = 1 + prefix.count("\n")
    last_nl = prefix.rfind("\n")
    column = pos + 1 if last_nl == -1 else pos - last_nl
    return line, column


def lex_error(source: str, pos: int, msg: str) -> None:
    line, col = position_to_line_col(source, pos)
    raise SyntaxError(f"Lexical error at line {line}, column {col} (position {pos}): {msg}")


# Lexical categories shown in Phase 1
_OPERATOR_TYPES = frozenset(
    {"PLUS", "MINUS", "STAR", "SLASH", "ASSIGN", "EQ", "NE", "LT", "LE", "GT", "GE"}
)
_SEPARATOR_TYPES = frozenset({"LPAREN", "RPAREN", "LBRACE", "RBRACE", "SEMI"})
_KEYWORD_TYPES = frozenset({"INT", "IF", "ELSE", "WHILE", "PRINT"})

_TOKEN_SYMBOL: dict[str, str] = {
    "PLUS": "+",
    "MINUS": "-",
    "STAR": "*",
    "SLASH": "/",
    "ASSIGN": "=",
    "EQ": "==",
    "NE": "!=",
    "LT": "<",
    "LE": "<=",
    "GT": ">",
    "GE": ">=",
    "LPAREN": "(",
    "RPAREN": ")",
    "LBRACE": "{",
    "RBRACE": "}",
    "SEMI": ";",
    "INT": "int",
    "IF": "if",
    "ELSE": "else",
    "WHILE": "while",
    "PRINT": "printf",
}


def token_category(token_type: str) -> str:
    """Main lexical class: Identifier, Operator, Separator, Number, or Keyword."""
    if token_type == "IDENT":
        return "Identifier"
    if token_type == "NUMBER":
        return "Number"
    if token_type in _KEYWORD_TYPES:
        return "Keyword"
    if token_type in _OPERATOR_TYPES:
        return "Operator"
    if token_type in _SEPARATOR_TYPES:
        return "Separator"
    return "Other"


def token_symbol(token: Token) -> str:
    """What the token represents (symbol or name)."""
    if token.type == "IDENT":
        return f"name: {token.value}"
    if token.type == "NUMBER":
        return f"value: {token.value}"
    if token.type in _KEYWORD_TYPES:
        return f"keyword: {token.value}"
    return _TOKEN_SYMBOL.get(token.type, token.value)


def format_tokens_table(tokens: List[Token]) -> str:
    lines = [
        "PHASE 1: LEXICAL ANALYZER",
        "Each word is classified as:",
        "  Identifier | Operator | Separator | Number | Keyword",
        "",
        f"{'#':>3}   {'Word':<10}  {'Category':<12}  Detail",
        "-" * 48,
    ]

    counts: dict[str, int] = {
        "Identifier": 0,
        "Operator": 0,
        "Separator": 0,
        "Number": 0,
        "Keyword": 0,
    }
    id_names: List[str] = []
    op_symbols: List[str] = []
    sep_symbols: List[str] = []

    n = 0
    for t in tokens:
        if t.type == "EOF":
            break
        n += 1
        word = t.value.replace("\n", "\\n").replace("\t", "\\t")
        cat = token_category(t.type)
        counts[cat] = counts.get(cat, 0) + 1
        if cat == "Identifier":
            id_names.append(word)
        elif cat == "Operator":
            op_symbols.append(_TOKEN_SYMBOL.get(t.type, word))
        elif cat == "Separator":
            sep_symbols.append(_TOKEN_SYMBOL.get(t.type, word))
        detail = token_symbol(t)
        lines.append(f"{n:>3}   {word:<10}  {cat:<12}  {detail}")

    lines.append("-" * 48)
    lines.append(f"Total tokens: {n}")
    lines.append("")
    lines.append("Count by category:")
    lines.append(f"  Identifiers : {counts['Identifier']}")
    lines.append(f"  Operators   : {counts['Operator']}")
    lines.append(f"  Separators  : {counts['Separator']}")
    lines.append(f"  Numbers     : {counts['Number']}")
    lines.append(f"  Keywords    : {counts['Keyword']}")
    if id_names:
        lines.append(f"  Identifier names: {', '.join(id_names)}")
    if op_symbols:
        lines.append(f"  Operators used : {', '.join(op_symbols)}")
    if sep_symbols:
        lines.append(f"  Separators used: {', '.join(sep_symbols)}")
    return "\n".join(lines)


def show_tokens(tokens: List[Token]) -> None:
    print(format_tokens_table(tokens))


def lex(source: str) -> List[Token]:
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

        if kind == "IDENT" and value in KEYWORDS:
            kind = KEYWORDS[value]
        
        # Reject Python keywords to ensure only C syntax is accepted
        if kind == "IDENT" and value in PYTHON_KEYWORDS:
            lex_error(source, pos, f"'{value}' is a Python keyword and is not allowed in C code")

        tokens.append(Token(kind, value, pos, line, column))

    end_pos = len(source)
    end_line, end_col = position_to_line_col(source, end_pos)
    tokens.append(Token("EOF", "", end_pos, end_line, end_col))
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
class CompareOp(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class Assign(ASTNode):
    name: str
    expr: ASTNode


@dataclass
class VarDecl(ASTNode):
    name: str
    init: Optional[ASTNode] = None


@dataclass
class PrintStmt(ASTNode):
    expr: ASTNode


@dataclass
class IfStmt(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None


@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode
    body: ASTNode


@dataclass
class Block(ASTNode):
    statements: List[ASTNode]


@dataclass
class Program(ASTNode):
    statements: List[ASTNode]


class Parser:
    """Recursive-descent parser building an AST from tokens."""

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
                f"Expected token {token_type}, got {t.type} at line {t.line}, column {t.column}"
            )
        return self.advance()

    def match(self, *token_types: TokenType) -> Optional[Token]:
        if self.current.type in token_types:
            return self.advance()
        return None

    def parse(self) -> Program:
        statements: List[ASTNode] = []
        while self.current.type != "EOF":
            statements.append(self.statement())
        return Program(statements)

    def statement(self) -> ASTNode:
        if self.current.type == "LBRACE":
            return self.block()
        if self.current.type == "INT":
            return self.var_decl()
        if self.current.type == "IF":
            return self.if_stmt()
        if self.current.type == "WHILE":
            return self.while_stmt()
        if self.current.type == "PRINT":
            return self.print_stmt()
        if self.current.type == "IDENT" and self._peek().type == "ASSIGN":
            name = self.advance().value
            self.expect("ASSIGN")
            expr = self.expr()
            self.expect("SEMI")
            return Assign(name, expr)

        t = self.current
        raise SyntaxError(
            f"Invalid statement starting with {t.type} at line {t.line}, column {t.column}"
        )

    def var_decl(self) -> VarDecl:
        self.expect("INT")
        name = self.expect("IDENT").value
        init: Optional[ASTNode] = None
        if self.match("ASSIGN"):
            init = self.expr()
        self.expect("SEMI")
        return VarDecl(name, init)

    def block(self) -> Block:
        self.expect("LBRACE")
        statements: List[ASTNode] = []
        while self.current.type not in ("RBRACE", "EOF"):
            statements.append(self.statement())
        self.expect("RBRACE")
        return Block(statements)

    def if_stmt(self) -> IfStmt:
        self.expect("IF")
        self.expect("LPAREN")
        condition = self.condition()
        self.expect("RPAREN")
        then_branch = self.statement()
        else_branch: Optional[ASTNode] = None
        if self.match("ELSE"):
            else_branch = self.statement()
        return IfStmt(condition, then_branch, else_branch)

    def while_stmt(self) -> WhileStmt:
        self.expect("WHILE")
        self.expect("LPAREN")
        condition = self.condition()
        self.expect("RPAREN")
        body = self.statement()
        return WhileStmt(condition, body)

    def print_stmt(self) -> PrintStmt:
        self.expect("PRINT")
        self.expect("LPAREN")
        expr = self.expr()
        self.expect("RPAREN")
        self.expect("SEMI")
        return PrintStmt(expr)

    def condition(self) -> ASTNode:
        left = self.expr()
        if self.current.type in ("EQ", "NE", "LT", "LE", "GT", "GE"):
            op_token = self.advance()
            right = self.expr()
            return CompareOp(op_token.type, left, right)
        return left

    def expr(self) -> ASTNode:
        node = self.term()
        while self.current.type in ("PLUS", "MINUS"):
            op_token = self.advance()
            node = BinaryOp(op_token.type, node, self.term())
        return node

    def term(self) -> ASTNode:
        node = self.factor()
        while self.current.type in ("STAR", "SLASH"):
            op_token = self.advance()
            node = BinaryOp(op_token.type, node, self.factor())
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
        if tok.type == "MINUS":
            self.advance()
            return BinaryOp("MINUS", Number(0), self.factor())
        raise SyntaxError(f"Unexpected token {tok.type} at line {tok.line}, column {tok.column}")

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
        if self.op in ("+", "-", "*", "/", "==", "!=", "<", "<=", ">", ">="):
            return f"{self.target} = {self.arg1} {self.op} {self.arg2}"
        if self.op == "CONST":
            return f"{self.target} = {self.arg1}"
        if self.op == "LABEL":
            return f"{self.target}:"
        if self.op == "JMP":
            return f"goto {self.target}"
        if self.op == "JZ":
            return f"ifz {self.arg1} goto {self.target}"
        if self.op == "PRINT":
            return f"printf {self.arg1}"
        return f"{self.target}: {self.op} {self.arg1 or ''} {self.arg2 or ''}".strip()


class CodeGenerator:
    """Generate three-address code from the AST."""

    def __init__(self):
        self.temp_counter = 0
        self.label_counter = 0
        self.instructions: List[Instruction] = []

    def new_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def new_label(self) -> str:
        self.label_counter += 1
        return f"L{self.label_counter}"

    def generate(self, node: ASTNode) -> Tuple[List[Instruction], List[str]]:
        self.temp_counter = 0
        self.label_counter = 0
        self.instructions = []
        results: List[str] = []

        if isinstance(node, Program):
            for stmt in node.statements:
                out = self._gen_node(stmt)
                if out is not None:
                    results.append(out)
        else:
            out = self._gen_node(node)
            if out is not None:
                results.append(out)
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
            op_map = {"PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/"}
            self.instructions.append(Instruction(temp, op_map[node.op], left, right))
            return temp

        if isinstance(node, CompareOp):
            left = self._gen_node(node.left)
            right = self._gen_node(node.right)
            temp = self.new_temp()
            cmp_map = {"EQ": "==", "NE": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="}
            self.instructions.append(Instruction(temp, cmp_map[node.op], left, right))
            return temp

        if isinstance(node, Assign):
            src = self._gen_node(node.expr)
            self.instructions.append(Instruction(node.name, "MOV", src))
            return node.name

        if isinstance(node, PrintStmt):
            value = self._gen_node(node.expr)
            self.instructions.append(Instruction("", "PRINT", value))
            return None

        if isinstance(node, Block):
            for stmt in node.statements:
                self._gen_node(stmt)
            return None

        if isinstance(node, IfStmt):
            cond = self._gen_node(node.condition)
            else_label = self.new_label()
            end_label = self.new_label()
            self.instructions.append(Instruction(else_label, "JZ", cond))
            self._gen_node(node.then_branch)
            if node.else_branch is not None:
                self.instructions.append(Instruction(end_label, "JMP"))
                self.instructions.append(Instruction(else_label, "LABEL"))
                self._gen_node(node.else_branch)
                self.instructions.append(Instruction(end_label, "LABEL"))
            else:
                self.instructions.append(Instruction(else_label, "LABEL"))
            return None

        if isinstance(node, WhileStmt):
            start_label = self.new_label()
            end_label = self.new_label()
            self.instructions.append(Instruction(start_label, "LABEL"))
            cond = self._gen_node(node.condition)
            self.instructions.append(Instruction(end_label, "JZ", cond))
            self._gen_node(node.body)
            self.instructions.append(Instruction(start_label, "JMP"))
            self.instructions.append(Instruction(end_label, "LABEL"))
            return None

        if isinstance(node, Program):
            return None

        if isinstance(node, VarDecl):
            if node.init is not None:
                src = self._gen_node(node.init)
                self.instructions.append(Instruction(node.name, "MOV", src))
            return node.name

        raise TypeError(f"Unsupported AST node: {type(node).__name__}")


# ========== SEMANTIC ANALYSIS PHASE ==========


@dataclass
class SemanticResult:
    ok: bool
    symbol_table: dict[str, str]
    messages: List[str]
    errors: List[str]


class SemanticError(Exception):
    """Raised when semantic analysis finds errors."""


class SemanticAnalyzer:
    """Check declarations, variable usage, and basic statement validity."""

    def __init__(self) -> None:
        self.symbols: dict[str, str] = {}
        self.messages: List[str] = []
        self.errors: List[str] = []

    def analyze(self, program: Program) -> SemanticResult:
        self.symbols = {}
        self.messages = []
        self.errors = []
        for stmt in program.statements:
            self._check_stmt(stmt)
        ok = len(self.errors) == 0
        if ok:
            self.messages.append("Semantic checks passed.")
        return SemanticResult(ok, dict(self.symbols), self.messages, self.errors)

    def _error(self, msg: str) -> None:
        self.errors.append(msg)

    def _check_stmt(self, node: ASTNode) -> None:
        if isinstance(node, VarDecl):
            if node.name in self.symbols:
                self._error(f"Variable '{node.name}' is already declared.")
            else:
                self.symbols[node.name] = "int"
                self.messages.append(f"Declared variable '{node.name}' as int.")
            if node.init is not None:
                self._check_expr(node.init)
            return

        if isinstance(node, Assign):
            if node.name not in self.symbols:
                self._error(f"Assignment to undeclared variable '{node.name}'.")
            self._check_expr(node.expr)
            return

        if isinstance(node, PrintStmt):
            self._check_expr(node.expr)
            return

        if isinstance(node, IfStmt):
            self._check_expr(node.condition)
            self._check_stmt(node.then_branch)
            if node.else_branch is not None:
                self._check_stmt(node.else_branch)
            return

        if isinstance(node, WhileStmt):
            self._check_expr(node.condition)
            self._check_stmt(node.body)
            return

        if isinstance(node, Block):
            for stmt in node.statements:
                self._check_stmt(stmt)
            return

    def _check_expr(self, node: ASTNode) -> None:
        if isinstance(node, Number):
            return
        if isinstance(node, Variable):
            if node.name not in self.symbols:
                self._error(f"Use of undeclared variable '{node.name}'.")
            return
        if isinstance(node, (BinaryOp, CompareOp)):
            self._check_expr(node.left)
            self._check_expr(node.right)
            return


def format_semantic(result: SemanticResult) -> str:
    lines = [
        "PHASE 3: SEMANTIC ANALYSIS",
        "Checks variables are declared before use.",
        "",
        "Variables in program:",
    ]
    if result.symbol_table:
        names = ", ".join(f"{n} ({t})" for n, t in sorted(result.symbol_table.items()))
        lines.append(f"  {names}")
    else:
        lines.append("  (none)")
    lines.append("")
    if result.errors:
        lines.append("Errors:")
        for err in result.errors:
            lines.append(f"  - {err}")
        lines.append("")
        lines.append("Result: FAILED")
    else:
        lines.append("Result: OK (no semantic errors)")
    return "\n".join(lines)


# ========== SIMPLE CODE OPTIMIZATION PHASE ==========


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
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
    if op == "==":
        return 1.0 if a == b else 0.0
    if op == "!=":
        return 1.0 if a != b else 0.0
    if op == "<":
        return 1.0 if a < b else 0.0
    if op == "<=":
        return 1.0 if a <= b else 0.0
    if op == ">":
        return 1.0 if a > b else 0.0
    if op == ">=":
        return 1.0 if a >= b else 0.0
    raise ValueError(f"Unknown op {op}")


def optimize_instructions(instructions: List[Instruction]) -> List[Instruction]:
    """Simple constant folding/propagation for straight-line arithmetic code."""
    const_values: dict[str, float] = {}
    optimized: List[Instruction] = []

    for instr in instructions:
        # Control flow boundaries: reset assumptions to stay safe.
        if instr.op in ("LABEL", "JMP", "JZ"):
            const_values.clear()
            optimized.append(instr)
            continue

        if instr.op == "CONST" and instr.arg1 is not None and _is_number(instr.arg1):
            const_values[instr.target] = float(instr.arg1)
            optimized.append(instr)
            continue

        if instr.op in ("+", "-", "*", "/", "==", "!=", "<", "<=", ">", ">="):
            a = instr.arg1
            b = instr.arg2
            if a is None or b is None:
                optimized.append(instr)
                continue
            a_val = float(a) if _is_number(a) else const_values.get(a)
            b_val = float(b) if _is_number(b) else const_values.get(b)
            if a_val is not None and b_val is not None:
                result = _eval_op(instr.op, a_val, b_val)
                const_values[instr.target] = result
                optimized.append(Instruction(instr.target, "CONST", str(result)))
            else:
                optimized.append(instr)
            continue

        if instr.op == "MOV":
            src = instr.arg1
            if src is not None and src in const_values:
                val = const_values[src]
                const_values[instr.target] = val
                optimized.append(Instruction(instr.target, "CONST", str(val)))
            else:
                optimized.append(instr)
            continue

        optimized.append(instr)

    return optimized


# ========== PUBLIC API / DRIVER ==========


def format_tokens(tokens: List[Token]) -> str:
    return format_tokens_table(tokens)


_OP_SYMBOL = {
    "PLUS": "+",
    "MINUS": "-",
    "STAR": "*",
    "SLASH": "/",
    "EQ": "==",
    "NE": "!=",
    "LT": "<",
    "LE": "<=",
    "GT": ">",
    "GE": ">=",
}


def _expr_summary(node: ASTNode) -> str:
    """One-line readable expression summary."""
    if isinstance(node, Number):
        return str(node.value)
    if isinstance(node, Variable):
        return node.name
    if isinstance(node, BinaryOp):
        return f"({_expr_summary(node.left)} {_OP_SYMBOL.get(node.op, node.op)} {_expr_summary(node.right)})"
    if isinstance(node, CompareOp):
        return f"({_expr_summary(node.left)} {_OP_SYMBOL.get(node.op, node.op)} {_expr_summary(node.right)})"
    return type(node).__name__


def _stmt_plain(n: ASTNode, index: int) -> str:
    if isinstance(n, VarDecl):
        if n.init is None:
            return f"{index}. declare int {n.name};"
        return f"{index}. declare int {n.name} = {_expr_summary(n.init)};"
    if isinstance(n, Assign):
        return f"{index}. {n.name} = {_expr_summary(n.expr)};"
    if isinstance(n, PrintStmt):
        return f"{index}. printf({_expr_summary(n.expr)});"
    if isinstance(n, IfStmt):
        text = f"{index}. if ({_expr_summary(n.condition)}) {{ ... }}"
        if n.else_branch is not None:
            text += " else { ... }"
        return text
    if isinstance(n, WhileStmt):
        return f"{index}. while ({_expr_summary(n.condition)}) {{ ... }}"
    if isinstance(n, Block):
        return f"{index}. {{ {len(n.statements)} statements }}"
    return f"{index}. {type(n).__name__}"


def format_ast(node: ASTNode) -> str:
    lines = [
        "PHASE 2: SYNTAX & AST",
        "Checks grammar and lists each statement.",
        "",
        "Statements:",
    ]
    if isinstance(node, Program):
        if not node.statements:
            lines.append("  (empty)")
        for i, stmt in enumerate(node.statements, start=1):
            lines.append(f"  {_stmt_plain(stmt, i)}")
    else:
        lines.append(f"  {_stmt_plain(node, 1)}")
    return "\n".join(lines)


def _instr_plain(instr: Instruction) -> str:
    """Short, readable line for intermediate code."""
    if instr.op == "LABEL":
        return f"[label {instr.target}]"
    if instr.op == "JMP":
        return f"go to {instr.target}"
    if instr.op == "JZ":
        return f"if {instr.arg1} is false, go to {instr.target}"
    if instr.op == "PRINT":
        return f"printf {instr.arg1}"
    return str(instr)


def format_codegen(instructions: List[Instruction]) -> str:
    lines = [
        "PHASE 4: CODE GENERATION",
        "Intermediate code (one step per line):",
        "",
    ]
    if not instructions:
        lines.append("  (nothing generated)")
    for i, instr in enumerate(instructions, start=1):
        lines.append(f"  {i}. {_instr_plain(instr)}")
    lines.append("")
    lines.append(f"Total: {len(instructions)} lines")
    return "\n".join(lines)


def format_optimized(raw: List[Instruction], optimized: List[Instruction]) -> str:
    lines = [
        "PHASE 5: OPTIMIZATION",
        "Final code after simplification:",
        "",
    ]
    if not optimized:
        lines.append("  (nothing to show)")
        return "\n".join(lines)

    changed = sum(
        1 for i in range(min(len(raw), len(optimized)))
        if str(raw[i]) != str(optimized[i])
    )
    for i, instr in enumerate(optimized, start=1):
        lines.append(f"  {i}. {_instr_plain(instr)}")
    lines.append("")
    if changed == 0:
        lines.append("No changes (same as Phase 4).")
    else:
        lines.append(f"Simplified {changed} line(s).")
    return "\n".join(lines)


def format_instructions(instructions: List[Instruction]) -> str:
    return format_codegen(instructions)


@dataclass
class CompileResult:
    tokens: List[Token]
    ast: Program
    semantic: SemanticResult
    raw_instructions: List[Instruction]
    optimized_instructions: List[Instruction]


def compile_program(source: str, *, stop_on_semantic_error: bool = True) -> CompileResult:
    """Run all compiler phases on full source code."""
    tokens = lex(source)
    ast = Parser(tokens).parse()
    semantic = SemanticAnalyzer().analyze(ast)
    if stop_on_semantic_error and not semantic.ok:
        raise SemanticError("Semantic analysis failed:\n" + "\n".join(semantic.errors))

    codegen = CodeGenerator()
    raw_instructions, _ = codegen.generate(ast)
    optimized_instructions = optimize_instructions(raw_instructions)
    return CompileResult(tokens, ast, semantic, raw_instructions, optimized_instructions)


def compile_source(source: str) -> Tuple[List[Instruction], List[Instruction]]:
    """Backward-compatible API: returns (raw TAC, optimized TAC)."""
    result = compile_program(source)
    return result.raw_instructions, result.optimized_instructions


def main() -> None:
    print("Enter full code. End input with an empty line:")
    lines: List[str] = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    source = "\n".join(lines)

    raw, optimized = compile_source(source)

    print("\n=== Raw three-address code ===")
    for instr in raw:
        print(str(instr))

    print("\n=== Optimized three-address code ===")
    for instr in optimized:
        print(str(instr))


if __name__ == "__main__":
    main()
