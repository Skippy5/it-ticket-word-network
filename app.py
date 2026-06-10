"""Streamlit app for interactive IT ticket word co-occurrence networks."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from clustering import apply_communities, cluster_terms
from cooccurrence import build_graph, graph_to_tables
from config import FILTER_COLUMNS, PipelineConfig, SYNONYMS, TEXT_COLUMNS
from drilldown import add_ticket_links, incidents_for_edge, incidents_for_term
from preprocess import parse_stopwords, parse_synonyms, process_tickets, read_ticket_csvs
from viz import build_pyvis_html


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"


st.set_page_config(page_title="IT Ticket Word Network", layout="wide")


def _demo_files() -> list[Path]:
    return sorted(DATA_DIR.glob("it_tickets_*.csv"))


@st.cache_data(show_spinner=False)
def load_demo(paths: list[str]) -> tuple[pd.DataFrame, list[str]]:
    return read_ticket_csvs(paths)


def filter_frame(frame: pd.DataFrame) -> pd.DataFrame:
    scoped = frame.copy()
    st.sidebar.subheader("Filters")
    if "opened_at" in scoped.columns:
        dates = pd.to_datetime(scoped["opened_at"], errors="coerce")
        if dates.notna().any():
            min_date = dates.min().date()
            max_date = dates.max().date()
            selected = st.sidebar.date_input("Opened date range", (min_date, max_date))
            if isinstance(selected, tuple) and len(selected) == 2:
                start, end = pd.to_datetime(selected[0]), pd.to_datetime(selected[1])
                scoped = scoped[(dates >= start) & (dates <= end + pd.Timedelta(days=1))]

    country_selected = None
    state_selected = None
    for col in FILTER_COLUMNS:
        if col not in scoped.columns:
            continue
        options_frame = scoped
        if col == "state" and country_selected and "country" in frame.columns:
            options_frame = frame[frame["country"].isin(country_selected)]
        if col == "location":
            options_frame = frame
            if country_selected and "country" in options_frame.columns:
                options_frame = options_frame[options_frame["country"].isin(country_selected)]
            if state_selected and "state" in options_frame.columns:
                options_frame = options_frame[options_frame["state"].isin(state_selected)]
        options = sorted(v for v in options_frame[col].dropna().astype(str).unique() if v)
        selected = st.sidebar.multiselect(col.replace("_", " ").title(), options)
        if selected:
            scoped = scoped[scoped[col].astype(str).isin(selected)]
        if col == "country":
            country_selected = selected
        if col == "state":
            state_selected = selected
    if st.sidebar.button("Reset filters"):
        st.rerun()
    return scoped


def download_button(label: str, data, filename: str, mime: str) -> None:
    st.download_button(label, data=data, file_name=filename, mime=mime)


def main() -> None:
    st.title("IT Ticket Word Co-occurrence Network")
    st.caption("Filter tickets first, then rebuild the traceable term network from the selected incidents.")

    demo_paths = _demo_files()
    uploaded = st.sidebar.file_uploader("Upload ticket CSV(s)", type="csv", accept_multiple_files=True)
    demo_choice = st.sidebar.selectbox(
        "Or use sample data",
        ["All sample CSVs"] + [path.name for path in demo_paths],
    )

    if uploaded:
        frame, warnings = read_ticket_csvs(uploaded)
    elif demo_paths:
        paths = demo_paths if demo_choice == "All sample CSVs" else [DATA_DIR / demo_choice]
        frame, warnings = load_demo([str(path) for path in paths])
    else:
        st.info("Upload one or more CSV files to begin.")
        return

    if frame.empty:
        st.warning("No ticket rows were loaded.")
        return
    for warning in warnings:
        st.warning(warning)

    total_count = len(frame)
    scoped = filter_frame(frame)
    st.sidebar.markdown(f"**Showing {len(scoped):,} of {total_count:,} incidents**")

    st.sidebar.subheader("Text pipeline")
    available_text = [col for col in TEXT_COLUMNS if col in frame.columns]
    text_columns = st.sidebar.multiselect(
        "Text columns used",
        available_text,
        default=available_text[:1] or available_text,
    )
    stopword_text = st.sidebar.text_area(
        "Editable stop words",
        value="\n".join(sorted(PipelineConfig().stopwords)),
        height=180,
    )
    synonym_text = st.sidebar.text_area(
        "Synonym map (JSON or key=value)",
        value=json.dumps(SYNONYMS, indent=2),
        height=180,
    )
    phrase_detection = st.sidebar.toggle("Phrase detection", value=True)
    cooccurrence_scope = st.sidebar.selectbox("Co-occurrence scope", ["document", "window"])
    window_size = st.sidebar.slider("Window size", 3, 25, 8)
    edge_weighting = st.sidebar.selectbox("Edge weighting", ["count", "pmi"])
    min_freq = st.sidebar.slider("Minimum term frequency", 1, 20, 3)
    min_edge = st.sidebar.number_input("Minimum edge weight", value=2.0, min_value=0.0, step=0.5)
    max_nodes = st.sidebar.slider("Max nodes", 20, 250, 80)
    resolution = st.sidebar.slider("Louvain resolution", 0.2, 3.0, PipelineConfig().louvain_resolution, 0.1)
    physics = st.sidebar.toggle("Physics", value=True)
    url_template = st.sidebar.text_input(
        "Ticket URL template", value=PipelineConfig().service_now_url_template
    )

    if scoped.empty:
        st.info("No incidents match the current filters. Reset filters or broaden the selection.")
        return
    if not text_columns:
        st.warning("Select at least one text column.")
        return

    config = PipelineConfig(
        text_columns=text_columns,
        stopwords=parse_stopwords(stopword_text),
        synonyms=parse_synonyms(synonym_text),
        phrase_detection=phrase_detection,
        cooccurrence_scope=cooccurrence_scope,
        window_size=window_size,
        edge_weighting=edge_weighting,
        min_term_frequency=min_freq,
        min_edge_weight=float(min_edge),
        max_nodes=max_nodes,
        louvain_resolution=resolution,
        service_now_url_template=url_template,
    )

    with st.spinner("Building sparse co-occurrence matrix and graph..."):
        processed = process_tickets(scoped, text_columns, config)
        graph = apply_communities(build_graph(processed.documents, config), resolution)
        nodes, edges = graph_to_tables(graph)

    left, mid, right = st.columns(3)
    left.metric("Incidents", f"{len(scoped):,}", f"of {total_count:,}")
    mid.metric("Terms", f"{len(nodes):,}")
    right.metric("Clusters", f"{len(cluster_terms(graph)):,}")

    if graph.number_of_nodes() == 0:
        st.info("No graph survived the current pruning settings. Lower min frequency or edge weight.")
        return

    incident_lookup = {
        str(row["ticket_id"]): {
            col: str(row.get(col, ""))
            for col in ["ticket_id", "short_description", "business_unit", "country", "state", "location"]
            if col in scoped.columns
        }
        for _, row in scoped.iterrows()
    }
    html = build_pyvis_html(
        graph, processed.term_ticket_ids, processed.ticket_terms, incident_lookup, physics
    )
    components.html(html, height=760, scrolling=True)

    tabs = st.tabs(["Drill-in", "Clusters", "Exports"])
    with tabs[0]:
        st.subheader("Node evidence")
        node_choice = st.selectbox(
            "Term",
            sorted(graph.nodes, key=lambda n: (-graph.nodes[n].get("frequency", 0), n)),
            format_func=lambda term: term.replace("_", " "),
        )
        term_rows = add_ticket_links(
            incidents_for_term(node_choice, processed.term_ticket_ids, scoped), url_template
        )
        st.dataframe(term_rows, use_container_width=True, hide_index=True)

        st.subheader("Edge evidence")
        edge_options = sorted(
            graph.edges,
            key=lambda e: (-graph.edges[e].get("weight", 0), e[0], e[1]),
        )
        edge_choice = st.selectbox(
            "Connection",
            edge_options,
            format_func=lambda e: f"{e[0].replace('_', ' ')} - {e[1].replace('_', ' ')}",
        )
        edge_rows = add_ticket_links(
            incidents_for_edge(edge_choice[0], edge_choice[1], processed.ticket_terms, scoped),
            url_template,
        )
        st.dataframe(edge_rows, use_container_width=True, hide_index=True)

    with tabs[1]:
        cluster_rows = [
            {
                "community": cid,
                "terms": ", ".join(term.replace("_", " ") for term in terms),
                "term_count": len(terms),
            }
            for cid, terms in cluster_terms(graph).items()
        ]
        st.dataframe(pd.DataFrame(cluster_rows), use_container_width=True, hide_index=True)

    with tabs[2]:
        nodes_df = pd.DataFrame(nodes)
        edges_df = pd.DataFrame(edges)
        if not edges_df.empty:
            edges_df["incident_ids"] = edges_df.apply(
                lambda row: ",".join(
                    incidents_for_edge(row["source"], row["target"], processed.ticket_terms, scoped)[
                        "ticket_id"
                    ].astype(str)
                ),
                axis=1,
            )
        filtered_df = add_ticket_links(scoped.copy(), url_template)
        download_button("Download filtered incidents CSV", filtered_df.to_csv(index=False), "filtered_incidents.csv", "text/csv")
        download_button("Download nodes CSV", nodes_df.to_csv(index=False), "nodes.csv", "text/csv")
        download_button("Download edges CSV", edges_df.to_csv(index=False), "edges.csv", "text/csv")
        bundle = {
            "nodes": nodes_df.to_dict(orient="records"),
            "edges": edges_df.to_dict(orient="records"),
            "filtered_incidents": filtered_df.to_dict(orient="records"),
        }
        download_button(
            "Download graph JSON",
            json.dumps(bundle, indent=2),
            "ticket_word_network.json",
            "application/json",
        )


if __name__ == "__main__":
    main()
