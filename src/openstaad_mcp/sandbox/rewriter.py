"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

AST rewriter that transforms natural ``staad.Geometry.GetNodeCount()``
syntax into ``_call("staad.Geometry.GetNodeCount")`` dispatches that
the Monty sandbox can route through the security-gated COM bridge.

This lets AI-generated code use the familiar OpenSTAAD API surface::

    geo = staad.Geometry
    count = geo.GetNodeCount()
    coords = staad.Geometry.GetNodeCoordinates(1)

…which the rewriter transparently converts to::

    geo = staad.Geometry          # bare attribute → left as-is (Monty input)
    count = _call("geo.GetNodeCount")
    coords = _call("staad.Geometry.GetNodeCoordinates", 1)

Only calls whose root name matches a registered proxy object are rewritten.
Bare attribute access is **not** rewritten — it resolves through Monty's
normal name lookup.
"""

from __future__ import annotations

import ast
import textwrap


class _MethodCallRewriter(ast.NodeTransformer):
    """Rewrite method calls on proxy objects into ``_call(...)`` dispatches.

    Transforms::

        obj.method(a, b)           → _call("obj.method", a, b)
        obj.sub.method(a)          → _call("obj.sub.method", a)
        x = obj.sub                → x = _call("obj.sub")
        obj.sub.attr               → _call("obj.sub.attr")  (in expr context)

    Only rewrites nodes whose attribute chain is rooted at a name in
    *proxy_names* or a known alias.  Pure name references (e.g. ``staad``)
    and calls on other names are untouched.
    """

    def __init__(self, proxy_names: frozenset[str]) -> None:
        self._proxy_names = proxy_names
        # Track variable names assigned from a proxy attribute
        # (e.g. ``geo = staad.Geometry`` → ``geo`` is an alias)
        self._aliases: dict[str, str] = {}  # alias → dotted source path

    # ------------------------------------------------------------------

    def _resolve_chain(self, node: ast.AST) -> str | None:
        """Return the dotted path if *node* is an attribute chain rooted
        at a proxy name or known alias, else ``None``.

        When the root is an alias (e.g. ``geo`` from ``geo = staad.Geometry``),
        the alias is expanded to the original proxy path so the dispatcher
        only ever sees ``staad.*`` paths.
        """
        parts: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if not isinstance(cur, ast.Name):
            return None
        root = cur.id
        if root in self._proxy_names:
            parts.append(root)
            parts.reverse()
            return ".".join(parts)
        if root in self._aliases:
            # Expand alias: geo.Method → staad.Geometry.Method
            parts.reverse()
            return self._aliases[root] + "." + ".".join(parts) if parts else self._aliases[root]
        return None

    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        """Detect and rewrite alias assignments like ``geo = staad.Geometry``.

        Transforms ``geo = staad.Geometry`` into ``geo = _call("staad.Geometry")``
        and registers ``geo`` as an alias.
        """
        # First recurse into child nodes
        self.generic_visit(node)
        # Only simple ``name = expr`` (single target, Name node)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Attribute):
            chain = self._resolve_chain(node.value)
            if chain is not None:
                alias_name = node.targets[0].id
                self._aliases[alias_name] = chain
                # Rewrite RHS: staad.Geometry → _dispatch("staad.Geometry")
                node.value = ast.Call(
                    func=ast.Name(id="_dispatch", ctx=ast.Load()),
                    args=[ast.Constant(value=chain)],
                    keywords=[],
                )
                ast.copy_location(node.value, node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        path = self._resolve_chain(node.func)
        if path is None:
            return node
        new_args: list[ast.expr] = [ast.Constant(value=path)]
        new_args.extend(node.args)
        new_call = ast.Call(
            func=ast.Name(id="_dispatch", ctx=ast.Load()),
            args=new_args,
            keywords=node.keywords,
        )
        return ast.copy_location(new_call, node)


def rewrite_proxy_calls(code: str, proxy_names: frozenset[str]) -> str:
    """Parse *code*, rewrite proxy method calls, return transformed source.

    Parameters
    ----------
    code:
        Python source code (as written by the LLM / user).
    proxy_names:
        Set of root variable names that should be treated as COM proxies
        (typically ``{"staad"}``).

    Returns
    -------
    str
        Transformed source where ``staad.Xyz.Method(...)`` calls are
        replaced with ``_call("staad.Xyz.Method", ...)``.
    """
    tree = ast.parse(textwrap.dedent(code))
    rewriter = _MethodCallRewriter(proxy_names)
    new_tree = rewriter.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)
