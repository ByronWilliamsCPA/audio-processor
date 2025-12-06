#!/usr/bin/env python3
"""Check that files using | union syntax have 'from __future__ import annotations'.

This script enforces a code quality standard to ensure that Python files using
the modern | union type syntax (introduced in Python 3.10) also include the
future annotations import for clarity and consistency.

NOTE: Python 3.14 deprecates 'from __future__ import annotations' (PEP 649),
but it will remain functional until at least Python 3.13 EOL in 2029. This
script will be updated when the ecosystem transitions to PEP 649's deferred
annotation evaluation. For now, continue using the future import for Python
3.10+ compatibility.

Usage:
    python scripts/check_type_hints.py [--fix]

Exit codes:
    0: All checks passed
    1: Violations found (or other errors)
"""

import argparse
import ast
import re
import sys
from pathlib import Path


class UnionSyntaxVisitor(ast.NodeVisitor):
    """AST visitor to detect | union syntax in type annotations."""

    def __init__(self) -> None:
        self.has_union_syntax = False

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Visit binary operations to detect | in type contexts."""
        if isinstance(node.op, ast.BitOr):
            # Check if this is likely a type annotation context
            # This is a heuristic - it will catch most cases
            self.has_union_syntax = True
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        """Visit function arguments with annotations."""
        if node.annotation:
            self.visit(node.annotation)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignments."""
        if node.annotation:
            self.visit(node.annotation)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions with return annotations."""
        if node.returns:
            self.visit(node.returns)
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            if arg.annotation:
                self.visit(arg.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self.visit(node.args.kwarg.annotation)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        self.visit_FunctionDef(node)  # type: ignore[arg-type]


def _is_future_annotations_import(node: ast.ImportFrom) -> bool:
    """Check if an ImportFrom node is 'from __future__ import annotations'.

    Args:
        node: The ImportFrom AST node to check

    Returns:
        True if this is the future annotations import, False otherwise
    """
    if node.module != "__future__":
        return False

    return any(alias.name == "annotations" for alias in node.names)


def has_future_annotations_import(content: str) -> bool:
    """Check if file has 'from __future__ import annotations'."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _is_future_annotations_import(node):
            return True

    return False


def has_union_pipe_syntax(content: str) -> bool:
    """Check if file uses | union syntax in type hints.

    Uses multiple detection methods:
    1. AST parsing to detect BinOp with BitOr in annotation contexts
    2. Regex pattern matching for common type hint patterns
    """
    # Method 1: AST-based detection
    try:
        tree = ast.parse(content)
        visitor = UnionSyntaxVisitor()
        visitor.visit(tree)
        if visitor.has_union_syntax:
            return True
    except SyntaxError:
        pass

    # Method 2: Regex patterns for common type hint usage
    # Match patterns like: ": int | str", "-> bool | None", "[int | float]"
    patterns = [
        r":\s*\w+\s*\|\s*\w+",  # : Type | Type
        r"->\s*\w+\s*\|\s*\w+",  # -> Type | Type
        r"\[\s*\w+\s*\|\s*\w+",  # [Type | Type
        r"=\s*\w+\s*\|\s*\w+",  # = Type | Type (in function params)
    ]

    for pattern in patterns:
        if re.search(pattern, content):
            return True

    return False


def check_file(file_path: Path) -> tuple[bool, str]:
    """Check a single Python file for union syntax compliance.

    Returns:
        (is_compliant, message): Tuple indicating compliance and message
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Error reading file: {e}"

    has_union = has_union_pipe_syntax(content)
    has_import = has_future_annotations_import(content)

    if has_union and not has_import:
        return False, "Uses | union syntax without 'from __future__ import annotations'"

    return True, "OK"


def _find_shebang_end(lines: list[str]) -> int:
    """Find the line index after the shebang, if present.

    Args:
        lines: List of file lines

    Returns:
        Index after shebang (1 if present, 0 otherwise)
    """
    if lines and lines[0].startswith("#!"):
        return 1
    return 0


def _find_docstring_end(content: str, start_index: int) -> int:
    """Find the line index after the module docstring, if present.

    Args:
        content: File content as string
        start_index: Index to start searching from

    Returns:
        Index after docstring, or start_index if no docstring found
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return start_index

    if not tree.body:
        return start_index

    first_node = tree.body[0]
    if isinstance(first_node, ast.Expr) and isinstance(first_node.value, ast.Constant):
        docstring_end = first_node.end_lineno or 0
        return max(start_index, docstring_end)

    return start_index


def _find_import_insertion_point(lines: list[str], start_index: int) -> int:
    """Find where to insert the future import after existing future imports.

    Args:
        lines: List of file lines
        start_index: Index to start searching from

    Returns:
        Index where import should be inserted
    """
    insert_index = start_index

    for i, line in enumerate(lines[start_index:], start=start_index):
        stripped = line.strip()

        # Skip existing __future__ imports
        if stripped.startswith("from __future__ import"):
            continue

        # Stop at first non-comment, non-empty line
        if stripped and not stripped.startswith("#"):
            insert_index = i
            break

    return insert_index


def _insert_import_line(lines: list[str], insert_index: int) -> list[str]:
    """Insert the future annotations import at the specified position.

    Args:
        lines: List of file lines
        insert_index: Index where import should be inserted

    Returns:
        Modified list of lines
    """
    import_line = "from __future__ import annotations\n"

    # Check if there's already a blank line before insertion point
    has_blank_before = insert_index > 0 and not lines[insert_index - 1].strip()

    lines.insert(insert_index, import_line)

    # Add blank line after if there wasn't one before
    if not has_blank_before:
        lines.insert(insert_index + 1, "\n")

    return lines


def _validate_file_path(file_path: Path) -> bool:
    """Validate that file path is within the current directory for security.

    Args:
        file_path: Path to validate

    Returns:
        True if path is safe, False otherwise
    """
    if not file_path.resolve().is_relative_to(Path.cwd()):
        print(
            f"Security: Path {file_path} is outside current directory",
            file=sys.stderr,
        )
        return False
    return True


def add_future_import(file_path: Path) -> bool:
    """Add 'from __future__ import annotations' to a file.

    Returns:
        True if the import was added, False otherwise
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Find insertion point step by step
        insert_index = _find_shebang_end(lines)
        insert_index = _find_docstring_end(content, insert_index)
        insert_index = _find_import_insertion_point(lines, insert_index)

        # Insert the import
        lines = _insert_import_line(lines, insert_index)

        # Validate and write
        if not _validate_file_path(file_path):
            return False

        file_path.write_text("".join(lines), encoding="utf-8")
        return True

    except Exception as e:
        print(f"Error adding import to {file_path}: {e}", file=sys.stderr)
        return False


def _collect_python_files(src_dir: Path, include_tests: bool) -> list[Path]:
    """Collect all Python files to check.

    Args:
        src_dir: Source directory to search
        include_tests: Whether to include test files

    Returns:
        List of Python file paths
    """
    python_files = []

    if src_dir.exists():
        python_files.extend(src_dir.rglob("*.py"))

    if include_tests:
        tests_dir = Path("tests")
        if tests_dir.exists():
            python_files.extend(tests_dir.rglob("*.py"))

    return python_files


def _should_skip_file(file_path: Path) -> bool:
    """Check if a file should be skipped during processing.

    Args:
        file_path: Path to check

    Returns:
        True if file should be skipped, False otherwise
    """
    return "__pycache__" in str(file_path)


def _process_single_file(
    file_path: Path, fix_mode: bool
) -> tuple[bool, str | None, bool]:
    """Process a single file for compliance and optionally fix it.

    Args:
        file_path: Path to the file to process
        fix_mode: Whether to attempt fixing violations

    Returns:
        Tuple of (is_compliant, error_message, was_fixed)
    """
    is_compliant, message = check_file(file_path)

    if is_compliant:
        return True, None, False

    # File is not compliant
    if not fix_mode:
        return False, message, False

    # Try to fix
    if add_future_import(file_path):
        print(f"✓ Fixed: {file_path}")
        return True, None, True

    # Fix failed
    print(f"✗ Failed to fix: {file_path}: {message}", file=sys.stderr)
    return False, message, False


def _process_files(
    python_files: list[Path], fix_mode: bool
) -> tuple[list[tuple[Path, str]], list[Path]]:
    """Process all Python files and collect results.

    Args:
        python_files: List of Python files to process
        fix_mode: Whether to attempt fixing violations

    Returns:
        Tuple of (violations list, fixed files list)
    """
    violations: list[tuple[Path, str]] = []
    fixed: list[Path] = []

    for file_path in python_files:
        if _should_skip_file(file_path):
            continue

        is_compliant, error_message, was_fixed = _process_single_file(
            file_path, fix_mode
        )

        if was_fixed:
            fixed.append(file_path)
        elif not is_compliant and error_message:
            violations.append((file_path, error_message))
            if not fix_mode:
                print(f"✗ {file_path}: {error_message}", file=sys.stderr)

    return violations, fixed


def _print_summary(violations: list[tuple[Path, str]], fixed: list[Path]) -> int:
    """Print summary of results and return exit code.

    Args:
        violations: List of violations found
        fixed: List of files fixed

    Returns:
        Exit code (0 for success, 1 for violations)
    """
    print()

    if violations:
        print(f"Found {len(violations)} violation(s):")
        for file_path, message in violations:
            print(f"  - {file_path}: {message}")
        print()
        print("Run with --fix to automatically add the import")
        return 1

    if fixed:
        print(f"Fixed {len(fixed)} file(s)")
        return 0

    print("All files compliant ✓")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for | union syntax with future annotations import"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically add 'from __future__ import annotations' to files",
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path("src"),
        help="Source directory to check (default: src)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Also check test files",
    )
    args = parser.parse_args()

    # Extract typed values from args
    src_dir: Path = args.src_dir  # type: ignore[assignment]
    include_tests: bool = args.include_tests  # type: ignore[assignment]
    fix_mode: bool = args.fix  # type: ignore[assignment]

    # Collect files to process
    python_files = _collect_python_files(src_dir, include_tests)

    if not python_files:
        print(f"No Python files found in {src_dir}", file=sys.stderr)
        return 1

    # Process files
    violations, fixed = _process_files(python_files, fix_mode)

    # Print summary and return exit code
    return _print_summary(violations, fixed)


if __name__ == "__main__":
    sys.exit(main())
