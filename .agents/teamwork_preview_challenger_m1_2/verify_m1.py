#!/usr/bin/env python3
"""
Verification Script for Milestone M1 (Pre-commit & CI/CD Setup).
This script performs static verification and AST validation of changed files.
"""

import ast
import sys

import yaml  # type: ignore[import-untyped]


def check_python_syntax(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            code = f.read()
        ast.parse(code, filename=filepath)
        print(f"PASS: {filepath} AST syntax check")
        return True
    except Exception as e:
        print(f"FAIL: {filepath} AST syntax error: {e}")
        return False


def check_yaml_syntax(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            yaml.safe_load(f)
        print(f"PASS: {filepath} YAML syntax check")
        return True
    except Exception as e:
        print(f"FAIL: {filepath} YAML syntax error: {e}")
        return False


if __name__ == "__main__":
    results = []
    results.append(check_python_syntax("src/graph_tools.py"))
    results.append(check_python_syntax("src/api/services/camara_service.py"))
    results.append(check_yaml_syntax(".pre-commit-config.yaml"))
    results.append(check_yaml_syntax(".github/workflows/ci.yml"))

    if all(results):
        print("ALL VERIFICATION CHECKS PASSED.")
    else:
        print("SOME VERIFICATION CHECKS FAILED.")
        sys.exit(1)
