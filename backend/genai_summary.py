"""
Generates the plain-language "how to fix this" summary.

Per the spec this is meant to run against a local Ollama instance with a
medium-ish model (e.g. gemma2:9b / gemma:20b). Ollama isn't guaranteed to
be running on every machine this Flask app is deployed to, so this module
degrades gracefully to a rule-based summary built from the same stats if
Ollama can't be reached.
"""
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:12b"
REQUEST_TIMEOUT = 60


def _build_prompt(readme_results, requirements_result) -> str:
    lines = ["You are reviewing a software repository's documentation and dependency hygiene.",
             "Give a short, practical summary (3-6 sentences) covering:",
             "1) how to fix any broken README links, 2) documentation quality/gaps,",
             "3) any missing requirements.txt entries, 4) general improvement suggestions.",
             "",
             "Findings:"]

    for rr in readme_results:
        if rr.ok:
            lines.append(f"- {rr.rel_path}: no broken links found.")
        else:
            for b in rr.broken_links:
                lines.append(f"- {rr.rel_path}: broken link '{b.text}' -> '{b.target}' ({b.reason}).")

    if requirements_result is None:
        pass
    elif not requirements_result.exists:
        mods = ", ".join(sorted(requirements_result.imported)) or "none detected"
        lines.append(f"- No requirements.txt found anywhere in the repo. Imports used: {mods}.")
    elif requirements_result.missing:
        lines.append(
            f"- {requirements_result.rel_path} is missing entries for: "
            + ", ".join(sorted(requirements_result.missing))
        )
    else:
        lines.append(f"- {requirements_result.rel_path} covers all detected imports.")

    return "\n".join(lines)


def _rule_based_summary(readme_results, requirements_result) -> str:
    parts = []

    broken_readmes = [r for r in readme_results if not r.ok]
    if broken_readmes:
        total = sum(len(r.broken_links) for r in broken_readmes)
        names = ", ".join(r.rel_path for r in broken_readmes)
        parts.append(
            f"Found {total} broken link(s) across {len(broken_readmes)} README file(s) ({names}). "
            "Fix these by correcting relative paths to point at files that actually exist, "
            "and updating or removing dead external URLs."
        )
    elif readme_results:
        parts.append("All README files checked out clean, no broken links detected.")
    else:
        parts.append("No README.md files were found in this repository, consider adding one.")

    if requirements_result is None:
        pass
    elif not requirements_result.exists:
        parts.append(
            "No requirements.txt was found at all. Create one and pin the packages the "
            "code actually imports so the project is installable."
        )
    elif requirements_result.missing:
        suggestions = ", ".join(
            requirements_result.suggestions.get(m, m) for m in requirements_result.missing
        )
        parts.append(
            f"{requirements_result.rel_path} is missing {len(requirements_result.missing)} "
            f"package(s) that the code imports: {suggestions}. Add these to requirements.txt."
        )
    else:
        parts.append(f"{requirements_result.rel_path} already covers every import detected in the code.")

    parts.append(
        "General improvement: keep README examples in sync with the code, and consider "
        "pinning requirements.txt versions for reproducible installs."
    )

    return " ".join(parts)


def generate_summary(readme_results, requirements_result, model: str = DEFAULT_MODEL) -> dict:
    """Returns {"text": str, "source": "ollama" | "rule-based", "model": str | None}."""
    prompt = _build_prompt(readme_results, requirements_result)

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "").strip()
        if text:
            return {"text": text, "source": "ollama", "model": model}
    except (requests.RequestException, ValueError):
        pass

    return {
        "text": _rule_based_summary(readme_results, requirements_result),
        "source": "rule-based",
        "model": None,
    }
