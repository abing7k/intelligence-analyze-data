import ast
import contextlib
import io
import multiprocessing as mp
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.preprocess_service import dataframe_records, to_jsonable

SAFE_IMPORTS = {"pandas", "numpy", "math", "statistics", "time"}
BANNED_IMPORT_MEMBERS = {
    "time": {"sleep"},
}
BANNED_NAMES = {
    "__import__",
    "eval",
    "exec",
    "open",
    "compile",
    "input",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "exit",
    "quit",
}
BANNED_ATTRIBUTES = {
    "system",
    "popen",
    "remove",
    "unlink",
    "rmdir",
    "mkdir",
    "chmod",
    "chown",
    "to_csv",
    "to_excel",
    "to_pickle",
    "to_parquet",
    "to_feather",
    "to_hdf",
    "to_sql",
    "read_csv",
    "read_excel",
    "read_pickle",
    "read_parquet",
    "read_sql",
    "sleep",
}
BANNED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "pathlib",
    "glob",
    "pickle",
    "builtins",
    "importlib",
}


@dataclass
class ExecutionResult:
    status: str
    table_result: list[dict[str, Any]]
    chart_spec: dict[str, Any]
    stdout: str
    error_message: str | None
    execution_time_ms: int


class SafetyVisitor(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in SAFE_IMPORTS:
                raise AppError(code="CODE_UNSAFE", message=f"Import is not allowed: {alias.name}", status_code=400)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".")[0]
        if module not in SAFE_IMPORTS:
            raise AppError(code="CODE_UNSAFE", message=f"Import is not allowed: {node.module}", status_code=400)
        banned_members = BANNED_IMPORT_MEMBERS.get(module, set())
        for alias in node.names:
            if alias.name in banned_members:
                raise AppError(
                    code="CODE_UNSAFE",
                    message=f"Import is not allowed: {node.module}.{alias.name}",
                    status_code=400,
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BANNED_NAMES or node.id.startswith("__"):
            raise AppError(code="CODE_UNSAFE", message=f"Unsafe name is not allowed: {node.id}", status_code=400)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") or node.attr in BANNED_ATTRIBUTES:
            raise AppError(code="CODE_UNSAFE", message=f"Unsafe attribute is not allowed: {node.attr}", status_code=400)
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        raise AppError(code="CODE_UNSAFE", message="Delete statements are not allowed.", status_code=400)


def validate_code_safety(code: str) -> None:
    lowered = code.lower()
    for module in BANNED_MODULES:
        if f"import {module}" in lowered or f"from {module}" in lowered:
            raise AppError(code="CODE_UNSAFE", message=f"Dangerous module is not allowed: {module}", status_code=400)
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise AppError(code="LLM_OUTPUT_INVALID", message=f"Generated code has invalid syntax: {exc}", status_code=502) from exc
    SafetyVisitor().visit(tree)


def execute_safe_code(df: pd.DataFrame, code: str) -> ExecutionResult:
    validate_code_safety(code)
    settings = get_settings()
    ctx = _multiprocessing_context()
    queue: mp.Queue = ctx.Queue()
    started = perf_counter()
    process = ctx.Process(target=_execute_in_child, args=(df, code, queue))
    process.start()
    process.join(settings.execution_timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(2)
        raise AppError(code="EXECUTION_TIMEOUT", message="Analysis code execution timed out.", status_code=408)

    if queue.empty():
        raise AppError(code="EXECUTION_FAILED", message="Analysis code did not return a result.", status_code=500)

    payload = queue.get()
    execution_time_ms = int((perf_counter() - started) * 1000)
    if payload["status"] != "success":
        raise AppError(
            code="EXECUTION_FAILED",
            message=payload.get("error_message") or "Generated code failed during execution.",
            status_code=400,
            details={"traceback": payload.get("traceback", "")[-2000:]},
        )

    return ExecutionResult(
        status="success",
        table_result=payload.get("table_result", []),
        chart_spec=payload.get("chart_spec", {}),
        stdout=payload.get("stdout", ""),
        error_message=None,
        execution_time_ms=execution_time_ms,
    )


def _execute_in_child(df: pd.DataFrame, code: str, queue: mp.Queue) -> None:
    stdout = io.StringIO()
    namespace: dict[str, Any] = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "result_table": None,
        "chart_spec": {},
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "print": print,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "__import__": _limited_import,
        },
    }
    try:
        with contextlib.redirect_stdout(stdout):
            exec(compile(code, "<generated-analysis>", "exec"), namespace)
        table_result = _normalize_result_table(namespace.get("result_table"))
        chart_spec = _normalize_chart_spec(namespace.get("chart_spec"))
        queue.put(
            {
                "status": "success",
                "table_result": table_result,
                "chart_spec": chart_spec,
                "stdout": stdout.getvalue()[-4000:],
            }
        )
    except Exception as exc:
        queue.put(
            {
                "status": "error",
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
                "stdout": stdout.getvalue()[-4000:],
            }
        )


def _multiprocessing_context():
    main_path = sys.argv[0]
    if (not main_path or main_path in {"-", "<stdin>"} or not Path(main_path).exists()) and "fork" in mp.get_all_start_methods():
        return mp.get_context("fork")
    return mp.get_context("spawn")


def _normalize_result_table(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, pd.Series):
        return dataframe_records(value.reset_index().rename(columns={0: "value"}), 200)
    if isinstance(value, pd.DataFrame):
        return dataframe_records(value, 200)
    if isinstance(value, dict):
        return [{str(key): to_jsonable(item)} for key, item in value.items()]
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            return [
                {str(key): to_jsonable(item_value) for key, item_value in item.items()}
                for item in value[:200]
            ]
        return [{"value": to_jsonable(item)} for item in value[:200]]
    return [{"value": to_jsonable(value)}]


def _normalize_chart_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): to_jsonable(item) for key, item in value.items()}


def _limited_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
    root = name.split(".")[0]
    if root not in SAFE_IMPORTS:
        raise ImportError(f"Import is not allowed: {name}")
    return __import__(name, globals, locals, fromlist, level)
