# IT Ticket Word Co-occurrence Network

Interactive Streamlit app for finding clustered problem themes in IT ticket exports while keeping every node and edge traceable back to incident numbers.

## Live Demo

GitHub Pages serves a standalone interactive demo generated from `it_tickets_large.csv`:

https://skippy5.github.io/it-ticket-word-network/

The hosted page is static HTML. Run the Streamlit app locally for uploads, filters, parameter tuning, exports, and regenerated networks.

## Setup

```bash
cd ~/.openclaw/artifacts/2026-06-10/it-ticket-word-network
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py --server.port 3011
```

The app works with the included sample CSVs in `data/` or uploaded ServiceNow-style CSVs.

## What It Does

- Loads one or more CSV exports and auto-detects expected column names case-insensitively.
- Filters incidents before network computation by business unit, country, state, location, category, assignment group, priority, status, and opened date range.
- Builds one document per ticket from selected text columns.
- Cleans HTML, URLs, email addresses, timestamps, standalone numbers, and incident IDs.
- Applies editable IT stop words and editable synonym mapping.
- Keeps configurable phrase detection so terms like `distribution_list`, `active_directory`, `print_queue`, and `blue_screen` survive as graph nodes.
- Builds a sparse binary document/window by term matrix, then computes co-occurrence via `X.T @ X`.
- Supports raw count and positive PMI edge weights.
- Clusters terms with Louvain community detection and colors nodes by community.
- Provides node and edge incident drill-in, including copyable IDs and configurable ServiceNow links.
- Exports filtered incidents, nodes, edges, and a combined JSON bundle.

## Standalone HTML

```bash
source .venv/bin/activate
python cli.py data/it_tickets_large---547779de-1bc4-45cc-81b1-367caece5ca5.csv -o network.html
```

Open `network.html` in a browser. Node and edge clicks show the incident evidence panel inside the graph.

## Notes

The Python pipeline is the source of truth. PyVis/vis.js is used only for the browser interaction layer because it gives drag, zoom, hover, physics, and click events without turning the app into a custom JavaScript project. D3 would be appropriate later if you want richer bidirectional callbacks.
