"""Impact cascade engine.

Given any cause node (a corridor closure, a country event, or a commodity
shock) this walks the India dependency graph and reports every downstream node
it reaches — commodities, Indian sectors, and macro variables — with a
severity score and the transmission path.

This is the "any cause anywhere -> everything affected in India" engine. It is
deterministic and explainable: severity is the product of edge weights along
the shortest/strongest path from the cause, with a per-hop decay so distant
second-order effects rank below direct hits.

The graph lives in data/fixtures/dependency_graph.json. The LLM narrative layer
consumes the structured output of resolve_cascade() to justify the chain.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_GRAPH_PATH = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "dependency_graph.json"

# Per-hop decay so a 4th-order macro effect doesn't outrank a direct commodity hit.
_HOP_DECAY = 0.85
# Below this accumulated severity an edge is not worth propagating further.
_MIN_SEVERITY = 0.02


@dataclass
class CascadeNode:
    """A node reached by the cascade, with how it was reached."""

    id: str
    kind: str  # cause | commodity | sector | macro
    label: str
    severity: float  # 0-1 accumulated transmission strength
    hop: int  # distance from the cause in edges
    via: list[str] = field(default_factory=list)  # mechanism strings along the path
    path: list[str] = field(default_factory=list)  # node ids from cause to here
    lag_days: int = 0  # cumulative lag along the path


@dataclass
class CascadeResult:
    cause_id: str
    cause_label: str
    nodes: list[CascadeNode]
    edges_used: list[dict[str, Any]]

    def by_kind(self, kind: str) -> list[CascadeNode]:
        return sorted(
            [n for n in self.nodes if n.kind == kind],
            key=lambda n: n.severity,
            reverse=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "causeId": self.cause_id,
            "causeLabel": self.cause_label,
            "affectedCommodities": [_node_dict(n) for n in self.by_kind("commodity")],
            "sectorImpacts": [_node_dict(n) for n in self.by_kind("sector")],
            "macroImpacts": [_node_dict(n) for n in self.by_kind("macro")],
            "edgesUsed": self.edges_used,
            "nodeCount": len(self.nodes),
        }


def _node_dict(n: CascadeNode) -> dict[str, Any]:
    return {
        "id": n.id,
        "label": n.label,
        "kind": n.kind,
        "severity": round(n.severity, 3),
        "hop": n.hop,
        "via": n.via,
        "path": n.path,
        "lagDays": n.lag_days,
    }


@lru_cache(maxsize=1)
def _load_graph() -> dict[str, Any]:
    if not _GRAPH_PATH.exists():
        raise FileNotFoundError(f"dependency graph missing at {_GRAPH_PATH}")
    return json.loads(_GRAPH_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _adjacency() -> dict[str, list[dict[str, Any]]]:
    graph = _load_graph()
    adj: dict[str, list[dict[str, Any]]] = {}
    for e in graph.get("edges", []):
        adj.setdefault(e["from"], []).append(e)
    return adj


@lru_cache(maxsize=1)
def _node_index() -> dict[str, dict[str, Any]]:
    graph = _load_graph()
    idx: dict[str, dict[str, Any]] = {}
    for cause in graph.get("causes", []):
        idx[cause["id"]] = {"kind": "cause", **cause}
    for c in graph.get("commodities", []):
        idx[c["id"]] = {"kind": "commodity", **c}
    for s in graph.get("sectors", []):
        idx[s["id"]] = {"kind": "sector", **s}
    for m in graph.get("macro", []):
        idx[m["id"]] = {"kind": "macro", **m}
    return idx


def list_causes() -> list[dict[str, Any]]:
    """All cause nodes the user can pick as the origin of a cascade."""
    graph = _load_graph()
    return [
        {
            "id": c["id"],
            "type": c.get("type", "cause"),
            "label": c["label"],
            "region": c.get("region", ""),
            "description": c.get("description", ""),
        }
        for c in graph.get("causes", [])
    ]


def cause_id_for_corridor(corridor: str) -> str:
    """Map a frontend corridor code (e.g. 'hormuz') to its cause node id."""
    return f"corridor:{corridor}"


def cause_id_for_commodity(commodity: str) -> str:
    """Map a commodity code to its node id (commodity shocks can be causes too)."""
    return f"commodity:{commodity}"


def resolve_cascade(cause_id: str, intensity: float = 1.0) -> CascadeResult:
    """Walk the dependency graph from cause_id and collect every node reached.

    Args:
        cause_id: a node id present in the graph (corridor:*, country:*, or
            commodity:* — a commodity can itself be the origin of a shock).
        intensity: 0-1 scalar applied to the cause's outbound severity.

    Returns:
        CascadeResult with every reachable India-side node, scored by the
        strongest transmission path (max-product over paths, with hop decay).
    """
    idx = _node_index()
    adj = _adjacency()

    if cause_id not in idx:
        raise KeyError(f"unknown cause node: {cause_id}")

    intensity = max(0.0, min(1.0, intensity))
    cause = idx[cause_id]

    # best[node_id] -> CascadeNode currently holding the strongest path to it
    best: dict[str, CascadeNode] = {}
    edges_used: dict[str, dict[str, Any]] = {}

    start = CascadeNode(
        id=cause_id,
        kind=cause["kind"],
        label=cause.get("label", cause_id),
        severity=intensity,
        hop=0,
        via=[],
        path=[cause_id],
        lag_days=0,
    )
    best[cause_id] = start

    # Dijkstra-like relaxation maximising the product of edge weights with decay.
    queue: deque[CascadeNode] = deque([start])
    while queue:
        cur = queue.popleft()
        for edge in adj.get(cur.id, []):
            target = edge["to"]
            if target not in idx:
                continue
            decay = _HOP_DECAY ** cur.hop
            new_sev = cur.severity * float(edge.get("weight", 0.0)) * decay
            if new_sev < _MIN_SEVERITY:
                continue
            existing = best.get(target)
            if existing is not None and existing.severity >= new_sev:
                continue
            tnode = idx[target]
            node = CascadeNode(
                id=target,
                kind=tnode["kind"],
                label=tnode.get("label", target),
                severity=new_sev,
                hop=cur.hop + 1,
                via=cur.via + [edge.get("mechanism", "")],
                path=cur.path + [target],
                lag_days=cur.lag_days + int(edge.get("lagDays", 0)),
            )
            best[target] = node
            edge_key = f"{edge['from']}->{edge['to']}"
            edges_used[edge_key] = {
                "from": edge["from"],
                "to": edge["to"],
                "weight": edge.get("weight", 0.0),
                "mechanism": edge.get("mechanism", ""),
                "lagDays": edge.get("lagDays", 0),
            }
            queue.append(node)

    nodes = [n for n in best.values() if n.id != cause_id]
    return CascadeResult(
        cause_id=cause_id,
        cause_label=cause.get("label", cause_id),
        nodes=nodes,
        edges_used=list(edges_used.values()),
    )


def cascade_summary_for_llm(result: CascadeResult) -> dict[str, Any]:
    """Compact structured payload the LLM narrative layer reasons over."""
    return {
        "cause": result.cause_label,
        "affectedCommodities": [
            {"commodity": n.label, "severity": round(n.severity, 2), "lagDays": n.lag_days}
            for n in result.by_kind("commodity")
        ],
        "sectorImpacts": [
            {
                "sector": n.label,
                "severity": round(n.severity, 2),
                "lagDays": n.lag_days,
                "transmission": " -> ".join(n.via) if n.via else "",
            }
            for n in result.by_kind("sector")
        ],
        "macroImpacts": [
            {"variable": n.label, "severity": round(n.severity, 2), "lagDays": n.lag_days}
            for n in result.by_kind("macro")
        ],
    }


__all__ = [
    "CascadeNode",
    "CascadeResult",
    "resolve_cascade",
    "list_causes",
    "cause_id_for_corridor",
    "cause_id_for_commodity",
    "cascade_summary_for_llm",
]
