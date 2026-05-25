"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

AST-based code validator for the execute_code sandbox.

Parses Python code and walks the AST to reject dangerous constructs.
Only code that interacts with the pre-injected ``staad`` object and
whitelisted builtins is allowed to pass.
"""

import ast
import re
from dataclasses import dataclass, field

from openstaad_mcp.sandbox.const import ALLOWED_DUNDER_NAMES, ALLOWED_MODULE_ATTRS, BLOCKED_ATTRS, BLOCKED_BUILTINS

_FORMAT_DUNDER_RE = re.compile(r"\{[^}]*\.__[a-zA-Z_][a-zA-Z0-9_]*__")


@dataclass
class ValidationError:
    """Describes a single violation found during validation."""

    line: int
    col: int
    message: str


@dataclass
class ValidationResult:
    """Outcome of validating a code snippet."""

    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        if self.is_valid:
            return "ok"
        parts = [f"  line {e.line}:{e.col} — {e.message}" for e in self.errors]
        return "Validation failed:\n" + "\n".join(parts)


class _Visitor(ast.NodeVisitor):
    """Walk the AST and collect violations."""

    def __init__(self) -> None:
        self.errors: list[ValidationError] = []

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _err(self, node: ast.AST, msg: str) -> None:
        self.errors.append(
            ValidationError(
                line=getattr(node, "lineno", 0),
                col=getattr(node, "col_offset", 0),
                message=msg,
            )
        )

    # ------------------------------------------------------------------
    # String constants — block format-string dunder traversal
    # ------------------------------------------------------------------
    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and _FORMAT_DUNDER_RE.search(node.value):
            self._err(node, "format strings containing dunder attribute access are not allowed")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # import statements
    # ------------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        self._err(node, "import statements are not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._err(node, "from...import statements are not allowed")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # dunder attribute access  (e.g. obj.__class__)
    # Defence-in-depth: statically reject non-whitelisted attribute access
    # on sandbox-injected modules accessed by their canonical Name.
    # Runtime enforcement is handled by _ModuleProxy in executor.py.
    # ------------------------------------------------------------------
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self._err(node, f"access to dunder attribute '{node.attr}' is not allowed")
        if node.attr in BLOCKED_ATTRS:
            self._err(node, f"access to attribute '{node.attr}' is not allowed")
        if isinstance(node.value, ast.Name) and node.value.id in ALLOWED_MODULE_ATTRS:
            allowed = ALLOWED_MODULE_ATTRS[node.value.id]
            if node.attr not in allowed:
                self._err(
                    node,
                    f"attribute '{node.attr}' is not available on '{node.value.id}' in the sandbox",
                )
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Name references — block dangerous builtins and dunder names
    # ------------------------------------------------------------------
    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BLOCKED_BUILTINS:
            self._err(node, f"reference to '{node.id}' is not allowed")
        if node.id.startswith("__") and node.id.endswith("__") and node.id not in ALLOWED_DUNDER_NAMES:
            self._err(node, f"reference to dunder name '{node.id}' is not allowed")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Function / method calls — block dangerous call targets
    # ------------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        # Direct call of a blocked name: eval(...)
        if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_BUILTINS:
            self._err(node, f"call to '{node.func.id}()' is not allowed")
        # Block str.format() and str.format_map() to prevent runtime dunder traversal
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("format", "format_map"):
            self._err(node, f"'{node.func.attr}()' calls are not allowed in the sandbox")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # String attribute construction via subscript on __builtins__ etc.
    # ------------------------------------------------------------------
    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Block __builtins__["eval"] style
        if isinstance(node.value, ast.Name) and node.value.id in BLOCKED_BUILTINS:
            self._err(node, f"subscript on '{node.value.id}' is not allowed")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Global / nonlocal — prevent scope escape
    # ------------------------------------------------------------------
    def visit_Global(self, node: ast.Global) -> None:
        self._err(node, "'global' statement is not allowed")
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self._err(node, "'nonlocal' statement is not allowed")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Async constructs — not needed, block to reduce attack surface
    # ------------------------------------------------------------------
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._err(node, "async function definitions are not allowed")
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._err(node, "async for is not allowed")
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._err(node, "async with is not allowed")
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        self._err(node, "await is not allowed")
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Decorators — prevent smuggling via @eval etc.
    # ------------------------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for dec in node.decorator_list:
            self._err(dec, "decorators are not allowed")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for dec in node.decorator_list:
            self._err(dec, "decorators are not allowed")
        self.generic_visit(node)


def validate_code(source: str) -> ValidationResult:
    """Parse *source* and validate it against the sandbox policy.

    Returns a :class:`ValidationResult` — check ``result.is_valid``
    before proceeding to execution.
    """
    result = ValidationResult()

    try:
        tree = ast.parse(source, filename="<sandbox>", mode="exec")
    except SyntaxError as exc:
        result.errors.append(
            ValidationError(
                line=exc.lineno or 0,
                col=exc.offset or 0,
                message=f"syntax error: {exc.msg}",
            )
        )
        return result

    visitor = _Visitor()
    visitor.visit(tree)
    result.errors = visitor.errors
    return result


def capture_last_expr(source: str) -> tuple[str, bool]:
    """If the last statement is an expression, rewrite it to store its value.

    Returns the (possibly rewritten) source and a flag indicating whether
    the rewrite was applied.
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return source, False

    if not tree.body:
        return source, False

    last = tree.body[-1]
    if not isinstance(last, ast.Expr):
        return source, False

    # Replace the last expression with: __result__ = <expr>
    assign = ast.Assign(
        targets=[ast.Name(id="__result__", ctx=ast.Store())],
        value=last.value,
        lineno=last.lineno,
        col_offset=last.col_offset,
    )
    ast.copy_location(assign, last)
    tree.body[-1] = assign
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), True
