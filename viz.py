"""PyVis network rendering with embedded incident drill-in."""

from __future__ import annotations

import json
from html import escape

import networkx as nx
from pyvis.network import Network


PALETTE = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#be123c",
    "#4d7c0f",
    "#7c3aed",
    "#0f766e",
]


def build_pyvis_html(
    graph: nx.Graph,
    term_ticket_ids: dict[str, set[str]],
    ticket_terms: dict[str, set[str]],
    incident_lookup: dict[str, dict],
    physics: bool = True,
) -> str:
    net = Network(height="720px", width="100%", bgcolor="#ffffff", font_color="#111827")
    net.barnes_hut(gravity=-22000, central_gravity=0.25, spring_length=145, spring_strength=0.04)
    net.toggle_physics(physics)

    for node, data in graph.nodes(data=True):
        neighbors = sorted(
            graph[node].items(), key=lambda item: item[1].get("weight", 0), reverse=True
        )[:6]
        top_neighbors = ", ".join(n.replace("_", " ") for n, _ in neighbors)
        community = int(data.get("community", 0))
        frequency = int(data.get("frequency", 1))
        label = data.get("label", node)
        title = (
            f"<b>{escape(label)}</b><br>"
            f"Frequency: {frequency}<br>"
            f"Community: {community}<br>"
            f"Top neighbors: {escape(top_neighbors)}"
        )
        net.add_node(
            node,
            label=label,
            title=title,
            value=max(2, frequency),
            color=PALETTE[community % len(PALETTE)],
            group=community,
        )

    for source, target, data in graph.edges(data=True):
        weight = float(data.get("weight", 1))
        count = int(data.get("count", weight))
        title = (
            f"{escape(source.replace('_', ' '))} - {escape(target.replace('_', ' '))}<br>"
            f"Weight: {weight}<br>Co-occurring incidents: {count}"
        )
        net.add_edge(source, target, value=max(1, weight), title=title)

    net.set_options(
        """
        {
          "interaction": {"hover": true, "navigationButtons": true, "multiselect": false},
          "nodes": {"borderWidth": 1, "font": {"size": 18, "face": "Inter"}},
          "edges": {"smooth": {"type": "dynamic"}, "color": {"color": "#9ca3af", "highlight": "#111827"}},
          "physics": {"stabilization": {"iterations": 160}}
        }
        """
    )
    html = net.generate_html(notebook=False)

    node_evidence = {
        term: sorted(term_ticket_ids.get(term, set())) for term in graph.nodes
    }
    edge_evidence = {}
    for source, target in graph.edges:
        ids = [
            ticket_id
            for ticket_id, terms in ticket_terms.items()
            if source in terms and target in terms
        ]
        edge_evidence[f"{source}|||{target}"] = sorted(ids)
        edge_evidence[f"{target}|||{source}"] = sorted(ids)

    payload = {
        "nodeEvidence": node_evidence,
        "edgeEvidence": edge_evidence,
        "incidents": incident_lookup,
    }
    panel = f"""
    <div id="evidence-panel" style="position:fixed;right:18px;top:18px;width:min(430px,34vw);max-height:82vh;overflow:auto;background:#ffffff;border:1px solid #d1d5db;border-radius:8px;padding:14px 16px;box-shadow:0 10px 30px rgba(15,23,42,.18);font-family:Inter,Arial,sans-serif;font-size:13px;color:#111827;z-index:9999">
      <div style="font-weight:700;margin-bottom:6px">Incident evidence</div>
      <div id="evidence-body">Click a node or edge to list source incidents.</div>
    </div>
    <script>
    const drillPayload = {json.dumps(payload)};
    function incidentRows(ids) {{
      if (!ids || ids.length === 0) return "<p>No incidents found.</p>";
      return ids.slice(0, 80).map(id => {{
        const item = drillPayload.incidents[id] || {{}};
        const desc = item.short_description || "";
        const meta = [item.business_unit, item.country, item.state, item.location].filter(Boolean).join(" | ");
        return `<div style="border-top:1px solid #e5e7eb;padding:8px 0">
          <button onclick="navigator.clipboard && navigator.clipboard.writeText('${{id}}')" style="font-weight:700;border:0;background:#eff6ff;color:#1d4ed8;padding:2px 6px;border-radius:4px;cursor:pointer">${{id}}</button>
          <div>${{desc}}</div><div style="color:#6b7280">${{meta}}</div></div>`;
      }}).join("") + (ids.length > 80 ? `<div style="margin-top:8px;color:#6b7280">Showing 80 of ${{ids.length}} incidents.</div>` : "");
    }}
    function setEvidence(title, ids) {{
      document.getElementById("evidence-body").innerHTML =
        `<div style="font-weight:600;margin-bottom:6px">${{title}}</div><div>${{ids.length}} incident(s)</div>` + incidentRows(ids);
    }}
    setTimeout(() => {{
      if (typeof network === "undefined") return;
      network.on("click", function(params) {{
        if (params.nodes && params.nodes.length) {{
          const term = params.nodes[0];
          setEvidence(term.replaceAll("_", " "), drillPayload.nodeEvidence[term] || []);
        }} else if (params.edges && params.edges.length) {{
          const edge = edges.get(params.edges[0]);
          const ids = drillPayload.edgeEvidence[edge.from + "|||" + edge.to] || [];
          setEvidence(edge.from.replaceAll("_", " ") + " - " + edge.to.replaceAll("_", " "), ids);
        }}
      }});
    }}, 250);
    </script>
    """
    return html.replace("</body>", panel + "</body>")
