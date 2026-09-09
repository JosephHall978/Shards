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

# Import name -> pip package name, for the common cases where they differ.
IMPORT_TO_PACKAGE = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "git": "GitPython",
    "jwt": "PyJWT",
    "Crypto": "pycryptodome",
    "cryptography": "cryptography",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "OpenSSL": "pyOpenSSL",
    "google": "google-cloud",
    "flask_sqlalchemy": "Flask-SQLAlchemy",
    "flask_cors": "Flask-Cors",
    "serial": "pyserial",
    "skimage": "scikit-image",
    "requests_oauthlib": "requests-oauthlib",
}

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


REQ_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def parse_requirements_file(path: str) -> Set[str]:
    declared = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                match = REQ_LINE_RE.match(line)
                if match:
                    # normalize for comparison: lowercase, - and _ treated the same
                    declared.add(match.group(1).lower().replace("_", "-"))
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
