"""
Walks a cloned repo and builds a plain list of nodes describing the file
tree. Colouring/classification decisions are layered on top later by
graph_builder.py, this module just describes *what* is on disk.
"""
import os
from dataclasses import dataclass, field
from typing import List

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}

PYTHON_EXTS = {".py", ".ipynb"}


@dataclass
class FileNode:
    rel_path: str          # path relative to repo root, "" for the root itself
    name: str
    is_dir: bool
    kind: str = "other"    # "folder" | "python" | "other" | "readme" | "requirements"
    ext: str = ""


@dataclass
class ScanResult:
    root: str
    nodes: List[FileNode] = field(default_factory=list)
    readme_paths: List[str] = field(default_factory=list)
    requirements_paths: List[str] = field(default_factory=list)
    python_paths: List[str] = field(default_factory=list)


def scan_repo(root: str) -> ScanResult:
    result = ScanResult(root=root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]

        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir

        if rel_dir:
            result.nodes.append(FileNode(
                rel_path=rel_dir,
                name=os.path.basename(rel_dir),
                is_dir=True,
                kind="folder",
            ))

        for fname in filenames:
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            ext = os.path.splitext(fname)[1].lower()
            lower = fname.lower()

            if lower == "readme.md":
                kind = "readme"
                result.readme_paths.append(rel_path)
            elif lower == "requirements.txt":
                kind = "requirements"
                result.requirements_paths.append(rel_path)
            elif ext in PYTHON_EXTS:
                kind = "python"
                result.python_paths.append(rel_path)
            else:
                kind = "other"

            result.nodes.append(FileNode(
                rel_path=rel_path,
                name=fname,
                is_dir=False,
                kind=kind,
                ext=ext,
            ))

    return result
