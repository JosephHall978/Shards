"""
Ties the whole Shards pipeline together:
  clone -> scan -> check requirements -> check READMEs -> build graph -> GenAI summary
The temp clone directory is always removed at the end (success or failure),
per the spec: "temp folder that gets cleared once details are completely collected."
"""
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

from . import cloner, scanner, readme_checker, requirements_checker, graph_builder, genai_summary


@dataclass
class PipelineResult:
    git_url: str
    ok: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0

    scan: object = None
    readme_results: List = field(default_factory=list)
    requirements_result: object = None
    graph: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def run_pipeline(git_url: str, check_remote_links: bool = True, use_genai: bool = True) -> PipelineResult:
    start = time.time()
    result = PipelineResult(git_url=git_url)

    repo_path = None
    try:
        repo_path = cloner.clone_repo(git_url)

        scan = scanner.scan_repo(repo_path)
        result.scan = scan

        result.readme_results = readme_checker.check_all_readmes(
            repo_path, scan.readme_paths, check_remote=check_remote_links
        )

        result.requirements_result = requirements_checker.check_requirements(
            repo_path, scan.python_paths, scan.requirements_paths
        )

        graph = graph_builder.build_graph(scan, result.readme_results, result.requirements_result)
        result.graph = graph_builder.graph_to_dict(graph)

        if use_genai:
            result.summary = genai_summary.generate_summary(
                result.readme_results, result.requirements_result
            )
        else:
            result.summary = {"text": "", "source": "skipped", "model": None}

    except cloner.CloneError as exc:
        result.ok = False
        result.error = str(exc)
    except Exception as exc:  # keep the app alive, surface the error in the report
        result.ok = False
        result.error = f"Unexpected error: {exc}"
    finally:
        # Per spec: clear the temp folder once every detail has been collected.
        if repo_path and os.path.isdir(repo_path):
            cloner.cleanup(repo_path)

    result.duration_seconds = round(time.time() - start, 2)
    return result
