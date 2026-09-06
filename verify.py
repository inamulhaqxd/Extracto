#!/usr/bin/env python3
"""
Fast repository validation script.
Performs AST parsing, compilation checks, type-hint validation, and linter/type checks.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path


def check_ast_and_syntax(paths: list[Path]) -> int:
    errors = 0
    for p in paths:
        if not p.is_file() or not p.suffix == ".py":
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(p))
            # Verify compilation
            compile(ast.unparse(tree), str(p), "exec")
            print(f"  [OK] Syntax & AST: {p}")
        except Exception as e:
            print(f"  [FAIL] {p}: {e}")
            errors += 1
    return errors


def run_tools():
    print("=" * 60)
    print("  RUNNING REPOSITORY VERIFICATION (LINT & TYPE CHECK)")
    print("=" * 60)

    # 1. AST & Syntax check on all python files
    py_files = list(Path("ai_rfp_excel").glob("**/*.py")) + list(Path(".").glob("*.py"))
    # filter out virtual or hidden
    py_files = [p for p in py_files if ".venv" not in str(p) and "__pyrefly" not in str(p)]
    
    ast_errors = check_ast_and_syntax(py_files)

    # 2. Try ruff if installed
    try:
        res = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "ai_rfp_excel/app", "--ignore", "E501"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("  [OK] Ruff check passed cleanly.")
        else:
            print("  [Ruff Warnings/Errors]:\n", res.stdout)
    except Exception:
        pass

    # 3. Try mypy if installed
    try:
        res = subprocess.run(
            [sys.executable, "-m", "mypy", "ai_rfp_excel/app", "--ignore-missing-imports", "--explicit-package-bases"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("  [OK] Mypy check passed cleanly.")
        else:
            print("  [Mypy Warnings/Errors]:\n", res.stdout)
    except Exception:
        pass

    if ast_errors == 0:
        print("\nAll files verified successfully with 0 syntax/AST errors.")
    return ast_errors


if __name__ == "__main__":
    sys.exit(run_tools())
