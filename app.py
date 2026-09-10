import json
import uuid

from flask import Flask, render_template, request, redirect, url_for

from backend.pipeline import run_pipeline

app = Flask(__name__)

# In-memory store of recent scan results, keyed by a short id.
# Fine for a single-user local tool; swap for a real store if this
# ever needs to serve concurrent users.
RESULTS_CACHE = {}
CACHE_MAX = 20


def _remember(result):
    result_id = uuid.uuid4().hex[:10]
    RESULTS_CACHE[result_id] = result
    if len(RESULTS_CACHE) > CACHE_MAX:
        oldest = next(iter(RESULTS_CACHE))
        RESULTS_CACHE.pop(oldest, None)
    return result_id


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    git_url = request.form.get("git_url", "").strip()
    check_remote_links = request.form.get("check_remote_links") == "on"
    use_genai = request.form.get("use_genai") == "on"

    if not git_url:
        return render_template("index.html", error="Enter a git repository URL.")

    result = run_pipeline(git_url, check_remote_links=check_remote_links, use_genai=use_genai)
    result_id = _remember(result)
    return redirect(url_for("report", result_id=result_id))


@app.route("/report/<result_id>")
def report(result_id):
    result = RESULTS_CACHE.get(result_id)
    if result is None:
        return redirect(url_for("index"))
    graph_json = json.dumps(result.graph) if result.ok else "{}"
    return render_template("report.html", result=result, graph_json=graph_json)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
