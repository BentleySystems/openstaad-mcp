# Builtins that are safe to expose in the sandbox.
ALLOWED_BUILTINS: frozenset[str] = frozenset(
    {
        "abs",
        "all",
        "any",
        "bin",
        "bool",
        "bytes",
        "chr",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "frozenset",
        "hash",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "oct",
        "ord",
        "pow",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        # Constants
        "True",
        "False",
        "None",
    }
)

# Builtin names that must never be called or referenced.
BLOCKED_BUILTINS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "open",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "memoryview",
        "classmethod",
        "staticmethod",
        "property",
        "super",
        "type",
        "__build_class__",
        "format",
    }
)

# Non-dunder attributes that must be blocked at the AST level
BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        # Generator / coroutine / async-generator frame access
        "gi_frame",
        "gi_code",
        "gi_yieldfrom",
        "cr_frame",
        "cr_code",
        "cr_origin",
        "ag_frame",
        "ag_code",
        # Frame object attributes
        "f_globals",
        "f_locals",
        "f_builtins",
        "f_code",
        "f_back",
        "f_trace",
        "f_lineno",
        # Code object attributes
        "co_consts",
        "co_names",
        "co_varnames",
        "co_freevars",
        "co_cellvars",
        "co_filename",
        "co_code",
        # Traceback attributes
        "tb_frame",
        "tb_next",
        "tb_lineno",
        # Type hierarchy traversal
        "mro",
        # pywin32 COM dispatch internals
        "_oleobj_",
        "_ApplyTypes_",
        "_FlagAsMethod",
        "_olerepr_",
        "_mapCachedItems_",
        "_builtMethods_",
        "_enum_",
        "_lazydata_",
    }
)

# Per-module attribute whitelists for modules injected into the sandbox.
# Used both here (AST-level static check) and in executor.py (_ModuleProxy
# runtime enforcement).  Only attributes listed here may be accessed on the
# corresponding module name when written as a direct Name reference.
ALLOWED_MODULE_ATTRS: dict[str, frozenset[str]] = {
    "json": frozenset({"dumps", "loads"}),
    "math": frozenset(
        {
            "pi",
            "e",
            "tau",
            "inf",
            "nan",
            "ceil",
            "floor",
            "trunc",
            "factorial",
            "gcd",
            "lcm",
            "comb",
            "perm",
            "fabs",
            "fmod",
            "remainder",
            "copysign",
            "fsum",
            "prod",
            "isqrt",
            "frexp",
            "ldexp",
            "modf",
            "nextafter",
            "ulp",
            "exp",
            "expm1",
            "log",
            "log2",
            "log10",
            "log1p",
            "pow",
            "sqrt",
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "atan2",
            "sinh",
            "cosh",
            "tanh",
            "asinh",
            "acosh",
            "atanh",
            "degrees",
            "radians",
            "hypot",
            "dist",
            "erf",
            "erfc",
            "gamma",
            "lgamma",
            "isfinite",
            "isinf",
            "isnan",
            "isclose",
        }
    ),
}

# Maximum size (chars) of captured stdout to prevent memory exhaustion.
MAX_EXECUTION_STDOUT = 256_000

# Maximum length for a single result value to prevent large injection payloads
MAX_RESULT_LENGTH = 100_000
