from pathlib import Path

from clustering import apply_communities
from cooccurrence import build_graph, graph_to_tables
from config import PipelineConfig
from drilldown import incidents_for_edge, incidents_for_term
from preprocess import process_tickets, read_ticket_csvs


def test_large_sample_builds_graph():
    root = Path(__file__).parent
    csv = next((root / "data").glob("it_tickets_large*.csv"))
    frame, warnings = read_ticket_csvs([str(csv)])
    assert "ticket_id" in frame.columns
    config = PipelineConfig(max_nodes=90, min_term_frequency=2, min_edge_weight=2.0)
    processed = process_tickets(frame, ["short_description", "work_notes", "close_notes"], config)
    graph = apply_communities(build_graph(processed.documents, config), 1.0)
    nodes, edges = graph_to_tables(graph)
    assert len(nodes) > 10
    assert len(edges) > 10
    assert any("outlook" in node["term"] or "email" in node["term"] for node in nodes)
    assert warnings == []


def test_drilldown_returns_incidents():
    root = Path(__file__).parent
    csv = next((root / "data").glob("it_tickets_messy*.csv"))
    frame, _ = read_ticket_csvs([str(csv)])
    config = PipelineConfig(max_nodes=80, min_term_frequency=2, min_edge_weight=1.0)
    processed = process_tickets(frame, config.text_columns, config)
    graph = apply_communities(build_graph(processed.documents, config), 1.0)
    term = next(iter(graph.nodes))
    assert not incidents_for_term(term, processed.term_ticket_ids, frame).empty
    source, target = next(iter(graph.edges))
    assert not incidents_for_edge(source, target, processed.ticket_terms, frame).empty


if __name__ == "__main__":
    test_large_sample_builds_graph()
    test_drilldown_returns_incidents()
    print("tests passed")
