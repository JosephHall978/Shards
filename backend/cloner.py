"""
Clones a git repository into a temporary directory.

The temp directory is owned by the caller (the pipeline in analyzer.py),
which is responsible for calling `cleanup()` once every detail has been
collected from the clone (per the ReadMe: "Git clone should keep files in
temp folder that gets cleared once details are completely collected.").
"""
import shutil
import tempfile

from git import Repo, GitCommandError


class CloneError(Exception):
    pass


def clone_repo(git_url: str) -> str:
    """Clone git_url into a fresh temp dir and return the local path."""
    temp_dir = tempfile.mkdtemp(prefix="shards_")
    try:
        Repo.clone_from(git_url, temp_dir, depth=1)
    except GitCommandError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise CloneError(f"Could not clone '{git_url}': {exc}") from exc
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise CloneError(f"Unexpected error cloning '{git_url}': {exc}") from exc
    return temp_dir


def cleanup(path: str) -> None:
    """Remove the temp clone dir once analysis is complete."""
    shutil.rmtree(path, ignore_errors=True)
