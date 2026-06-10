"""Build a standalone ticket word network HTML file from CSV input."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clustering import apply_communities
from cooccurrence import build_graph
from config import PipelineConfig
from preprocess import process_tickets, read_ticket_csvs
from viz import build_pyvis_html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="+", help="Input ticket CSV(s)")
    parser.add_argument("-o", "--output", default="network.html")
    parser.add_argument("--max-nodes", type=int, default=80)
    parser.add_argument("--min-frequency", type=int, default=3)
    parser.add_argument("--min-edge-weight", type=float, default=2.0)
    parser.add_argument("--weighting", choices=["count", "pmi"], default="count")
    args = parser.parse_args()

    frame, warnings = read_ticket_csvs(args.csv)
    for warning in warnings:
        print(f"warning: {warning}")
    config = PipelineConfig(
        max_nodes=args.max_nodes,
        min_term_frequency=args.min_frequency,
        min_edge_weight=args.min_edge_weight,
        edge_weighting=args.weighting,
    )
    processed = process_tickets(frame, config.text_columns, config)
    graph = apply_communities(build_graph(processed.documents, config), config.louvain_resolution)
    incident_lookup = {
        str(row["ticket_id"]): {
            col: str(row.get(col, ""))
            for col in ["ticket_id", "short_description", "business_unit", "country", "state", "location"]
            if col in frame.columns
        }
        for _, row in frame.iterrows()
    }
    html = build_pyvis_html(
        graph, processed.term_ticket_ids, processed.ticket_terms, incident_lookup, physics=True
    )
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Wrote {args.output} with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")


if __name__ == "__main__":
    main()
