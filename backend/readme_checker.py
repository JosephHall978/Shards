"""
Checks every README.md found in the repo for broken links:
 - relative/local links that point at a file which doesn't exist
 - http(s) links that 404 (or otherwise fail to resolve)
"""
import os
import re
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

import requests

# Matches [text](target) and [text](target "title")
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(\s*<?([^)\s"]+)>?(?:\s+"[^"]*")?\s*\)')

REQUEST_TIMEOUT = 5


@dataclass
class BrokenLink:
    text: str
    target: str
    reason: str          # "404" | "local file missing" | "connection error" | etc.
    is_remote: bool


@dataclass
class ReadmeResult:
    rel_path: str
    links_checked: int = 0
    broken_links: List[BrokenLink] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.broken_links


def _is_remote(target: str) -> bool:
    scheme = urlparse(target).scheme
    return scheme in ("http", "https")

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

def _check_remote(url: str) -> str | None:
    """Return an error string if the URL is broken, else None."""
    try:
        resp = requests.head(url, headers=UA, allow_redirects=True, timeout=REQUEST_TIMEOUT, stream=True)
        if resp.status_code == 405:  # some servers reject HEAD, retry with GET
            resp = requests.get(url, headers=UA, allow_redirects=True, timeout=REQUEST_TIMEOUT, stream=True)
        if resp.status_code >= 400:
            return f"HTTP {resp.status_code}"
        return None
    except requests.RequestException as exc:
        return f"connection error ({exc.__class__.__name__})"


def _check_local(repo_root: str, readme_rel_path: str, target: str) -> str | None:
    """Return an error string if the local target is missing, else None."""
    # strip anchors/query strings
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean:
        return None  # pure anchor link, nothing to check on disk

    readme_dir = os.path.dirname(os.path.join(repo_root, readme_rel_path))
    candidate = os.path.normpath(os.path.join(readme_dir, clean))

    if not candidate.startswith(os.path.normpath(repo_root)):
        return None  # points outside the repo, not our concern

    if not os.path.exists(candidate):
        return "local file missing"
    return None


def check_readme(repo_root: str, readme_rel_path: str, check_remote: bool = True) -> ReadmeResult:
    full_path = os.path.join(repo_root, readme_rel_path)
    result = ReadmeResult(rel_path=readme_rel_path)

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return result

    for match in MD_LINK_RE.finditer(text):
        link_text, target = match.group(1), match.group(2)
        target = target.strip()
        if not target or target.startswith("mailto:"):
            continue

        result.links_checked += 1
        remote = _is_remote(target)

        if remote:
            if not check_remote:
                continue
            error = _check_remote(target)
        else:
            error = _check_local(repo_root, readme_rel_path, target)

        if error:
            result.broken_links.append(BrokenLink(
                text=link_text or target,
                target=target,
                reason=error,
                is_remote=remote,
            ))

    return result


def check_all_readmes(repo_root: str, readme_paths: List[str], check_remote: bool = True) -> List[ReadmeResult]:
    return [check_readme(repo_root, path, check_remote=check_remote) for path in readme_paths]
