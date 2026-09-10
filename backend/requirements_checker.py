"""
Finds every top-level import used across the repo's .py files, and
compares that against what's declared in requirements.txt (if any),
flagging anything missing and suggesting the pip package name to add.
"""
import ast
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Set
import tomllib
import json


def load_import_map(json_path: str = "./backend/pip_to_import.json") -> Dict[str, str]:
    """Loads the import-to-package mapping from a JSON file."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Mapping file not found at {json_path}")

    with open(json_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# Usage
IMPORT_TO_PACKAGE = load_import_map()

# Best-effort stdlib module list; falls back to sys.stdlib_module_names on 3.10+.
STDLIB_MODULES: Set[str] = set(getattr(sys, "stdlib_module_names", ()))
STDLIB_MODULES |= {"__future__", "_thread", "setuptools", "pkg_resources"}


@dataclass
class RequirementsResult:
    rel_path: str | None                   # None if no requirements.txt exists anywhere
    declared: Set[str] = field(default_factory=set)
    imported: Set[str] = field(default_factory=set)
    missing: List[str] = field(default_factory=list)     # import names not declared
    suggestions: Dict[str, str] = field(default_factory=dict)  # import name -> pip package

    @property
    def exists(self) -> bool:
        return self.rel_path is not None

    @property
    def ok(self) -> bool:
        return self.exists and not self.missing


def _top_level_module(dotted: str) -> str:
    return dotted.split(".")[0]


def extract_imports(py_path: str) -> Set[str]:
    """Return the set of top-level third-party module names imported by a file."""
    modules: Set[str] = set()
    try:
        with open(py_path, "r", encoding="utf-8", errors="ignore") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=py_path)
    except (SyntaxError, OSError, ValueError):
        return modules

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(_top_level_module(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import, e.g. "from . import x" -> not a dependency
            if node.module:
                modules.add(_top_level_module(node.module))

    return {m for m in modules if m and m not in STDLIB_MODULES}

PACKAGE_NAME_RE = re.compile(r"^\s*([a-zA-Z0-9_\-\.]+)")

def parse_requirement_line(line: str) -> str | None:
    """Extracts and normalizes the base package name from a dependency string."""
    # Strip comments and excess whitespace
    line = line.split("#", 1)[0].strip()

    # Ignore empty lines or pip flags (-r, -e, --extra-index-url, etc.)
    if not line or line.startswith("-"):
        return None

    match = PACKAGE_NAME_RE.match(line)
    if match:
        return match.group(1)
    return None


def parse_requirements_file(path: str) -> Set[str]:
    declared: Set[str] = set()

    if not os.path.exists(path):
        return declared

    # Handle pyproject.toml
    if path.endswith(".toml"):
        try:
            with open(path, "rb") as fh:
                data = tomllib.load(fh)

            # 1. Standard PEP 621 dependencies: [project.dependencies]
            project = data.get("project", {})
            raw_deps = list(project.get("dependencies", []))

            # Optional dependencies: [project.optional-dependencies]
            for opt_deps in project.get("optional-dependencies", {}).values():
                raw_deps.extend(opt_deps)

            # 2. Poetry dependencies: [tool.poetry.dependencies]
            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            for pkg, spec in poetry_deps.items():
                if pkg.lower() != "python":
                    declared.add(pkg)

            # Process collected PEP 621 / standard strings
            for dep in raw_deps:
                pkg_name = parse_requirement_line(dep)
                if pkg_name:
                    declared.add(pkg_name)

        except (OSError, tomllib.TOMLDecodeError):
            pass
        return declared

    # Handle requirements.txt / standard setup files
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                pkg_name = parse_requirement_line(line)
                if pkg_name:
                    declared.add(pkg_name)
    except OSError:
        pass

    return declared



def _package_is_declared(package_name: str, declared: Set[str]) -> bool:
    normalized = package_name.lower().replace("_", "-")
    return normalized in declared


def check_requirements(repo_root: str, python_paths: List[str], requirements_paths: List[str]) -> RequirementsResult:
    imported: Set[str] = set()
    for rel_path in python_paths:
        if not rel_path.endswith(".py"):
            continue  # skip notebooks for import extraction, ast can't parse .ipynb directly
        imported |= extract_imports(os.path.join(repo_root, rel_path))

    if not requirements_paths:
        result = RequirementsResult(rel_path=None, imported=imported)
        for mod in sorted(imported):
            pkg = IMPORT_TO_PACKAGE.get(mod, mod)
            result.missing.append(mod)
            result.suggestions[mod] = pkg
        return result

    # use the top-level (or first found) requirements.txt as the canonical one
    primary = sorted(requirements_paths, key=lambda p: p.count(os.sep))[0]
    declared = parse_requirements_file(os.path.join(repo_root, primary))

    result = RequirementsResult(rel_path=primary, declared=declared, imported=imported)

    for mod in sorted(imported):
        pkg = IMPORT_TO_PACKAGE.get(mod, mod)
        if not _package_is_declared(pkg, declared) and not _package_is_declared(mod, declared):
            result.missing.append(mod)
            result.suggestions[mod] = pkg

    return result
