"""
Builds the vis-network graph data (nodes + edges) using the colouring
rules from the ReadMe spec:

ReadMe colouring:
  - orange: README containing a broken link
  - dashed line: from README to where the link was expected to go
  - red: the missing/broken resource itself
  - green: README with no missing links

Requirements colouring:
  - orange: requirements.txt missing imports
  - red: no requirements.txt at all
  - green: requirements.txt present with no issues

General colouring:
  - purple: folders
  - blue: python/notebook files
  - pink: other file types
"""
from dataclasses import dataclass, field
from typing import Dict, List

COLORS = {
    "folder": "#8e44ad",       # purple
    "python": "#3498db",       # blue
    "other": "#e6a4c4",        # pink
    "readme_ok": "#2ecc40",    # green
    "readme_broken": "#e67e22",  # orange
    "requirements_ok": "#2ecc40",     # green
    "requirements_missing_some": "#e67e22",  # orange
    "requirements_missing_all": "#e74c3c",   # red
    "missing_resource": "#e74c3c",    # red
}


@dataclass
class GraphData:
    nodes: List[dict] = field(default_factory=list)
    edges: List[dict] = field(default_factory=list)
    _node_ids: set = field(default_factory=set)

    def add_node(self, node_id, label, color, shape="dot", title=None, size=None):
        if node_id in self._node_ids:
            return
        self._node_ids.add(node_id)
        node = {"id": node_id, "label": label, "color": color, "shape": shape}
        if title:
            node["title"] = title
        if size:
            node["size"] = size
        self.nodes.append(node)

    def add_edge(self, source, target, dashed=False, color=None):
        edge = {"from": source, "to": target}
        if dashed:
            edge["dashes"] = True
        if color:
            edge["color"] = color
        self.edges.append(edge)


def _folder_of(rel_path: str) -> str:
    if "/" not in rel_path and "\\" not in rel_path:
        return ""  # root
    return rel_path.rsplit("/", 1)[0] if "/" in rel_path else rel_path.rsplit("\\", 1)[0]


def build_graph(scan_result, readme_results, requirements_result) -> GraphData:
    graph = GraphData()
    graph.add_node("__root__", "repo", COLORS["folder"], shape="box", size=25)

    readme_by_path = {r.rel_path: r for r in readme_results}

    # every file/folder node from the scan
    for node in scan_result.nodes:
        parent = _folder_of(node.rel_path)
        parent_id = parent if parent else "__root__"

        if node.is_dir:
            graph.add_node(node.rel_path, node.name, COLORS["folder"], shape="box")

        if node.kind == "readme":
            rr = readme_by_path.get(node.rel_path)
            broken = bool(rr and not rr.ok)
            color = COLORS["readme_broken"] if broken else COLORS["readme_ok"]
            title = f"{len(rr.broken_links)} broken link(s)" if rr and broken else "No broken links"
            graph.add_node(node.rel_path, node.name, color, shape="ellipse", title=title)
        elif node.kind == "requirements":
            if requirements_result and requirements_result.exists and node.rel_path == requirements_result.rel_path:
                if requirements_result.ok:
                    color = COLORS["requirements_ok"]
                    title = "All imports satisfied"
                else:
                    color = COLORS["requirements_missing_some"]
                    title = f"{len(requirements_result.missing)} missing import(s)"
            else:
                color = COLORS["other"]
                title = None
            graph.add_node(node.rel_path, node.name, color, shape="ellipse", title=title)
        elif node.kind == "python":
            graph.add_node(node.rel_path, node.name, COLORS["python"])
        else:
            graph.add_node(node.rel_path, node.name, COLORS["other"])

        graph.add_edge(parent_id, node.rel_path)

    # if no requirements.txt exists anywhere, add a virtual red node hanging off root
    if requirements_result and not requirements_result.exists:
        graph.add_node("__no_requirements__", "requirements.txt (missing)",
                        COLORS["requirements_missing_all"], shape="ellipse",
                        title=f"{len(requirements_result.missing)} import(s) with nothing declared")
        graph.add_edge("__root__", "__no_requirements__", dashed=True, color=COLORS["missing_resource"])

    # dashed red edges from each broken README to the missing target it points at
    for rr in readme_results:
        for i, broken in enumerate(rr.broken_links):
            target_id = f"missing::{rr.rel_path}::{i}"
            label = broken.target if len(broken.target) <= 40 else broken.target[:37] + "..."
            title = f"{broken.reason} ({'remote' if broken.is_remote else 'local'})"
            graph.add_node(target_id, label, COLORS["missing_resource"], shape="triangle", title=title)
            graph.add_edge(rr.rel_path, target_id, dashed=True, color=COLORS["missing_resource"])

    return graph


def graph_to_dict(graph: GraphData) -> Dict:
    return {"nodes": graph.nodes, "edges": graph.edges}
