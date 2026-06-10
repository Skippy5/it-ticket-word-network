"""Sparse co-occurrence matrix and graph construction."""

from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix

from config import PipelineConfig


def document_windows(document: list[str], scope: str, window_size: int) -> list[set[str]]:
    if scope == "window" and window_size > 1:
        return [set(document[i : i + window_size]) for i in range(max(1, len(document) - window_size + 1))]
    return [set(document)]


def term_frequencies(documents: list[list[str]], scope: str = "document") -> Counter[str]:
    counts: Counter[str] = Counter()
    for doc in documents:
        terms = set(doc) if scope == "document" else doc
        counts.update(terms)
    return counts


def select_terms(documents: list[list[str]], config: PipelineConfig) -> list[str]:
    freqs = term_frequencies(documents)
    terms = [term for term, count in freqs.items() if count >= config.min_term_frequency]
    terms.sort(key=lambda term: (-freqs[term], term))
    return terms[: config.max_nodes]


def build_sparse_matrix(
    documents: list[list[str]], terms: list[str], config: PipelineConfig
) -> tuple[csr_matrix, list[str]]:
    vocab = {term: i for i, term in enumerate(terms)}
    rows: list[int] = []
    cols: list[int] = []
    row_count = 0
    for doc in documents:
        for window_terms in document_windows(doc, config.cooccurrence_scope, config.window_size):
            selected = {vocab[t] for t in window_terms if t in vocab}
            for col in selected:
                rows.append(row_count)
                cols.append(col)
            row_count += 1
    data = np.ones(len(rows), dtype=np.int8)
    matrix = csr_matrix((data, (rows, cols)), shape=(row_count, len(terms)), dtype=np.int8)
    return matrix, terms


def build_graph(documents: list[list[str]], config: PipelineConfig) -> nx.Graph:
    terms = select_terms(documents, config)
    graph = nx.Graph()
    if not terms:
        return graph

    X, terms = build_sparse_matrix(documents, terms, config)
    cooc = (X.T @ X).tocoo()
    freqs = np.asarray(X.sum(axis=0)).ravel()
    n_docs = max(1, X.shape[0])

    for idx, term in enumerate(terms):
        graph.add_node(term, label=term.replace("_", " "), frequency=int(freqs[idx]))

    for i, j, count in zip(cooc.row, cooc.col, cooc.data, strict=False):
        if i >= j or count <= 0:
            continue
        if config.edge_weighting == "pmi":
            raw = (float(count) * n_docs) / max(float(freqs[i] * freqs[j]), 1.0)
            weight = max(0.0, math.log2(raw)) if raw > 0 else 0.0
        else:
            weight = float(count)
        if weight >= config.min_edge_weight:
            graph.add_edge(terms[i], terms[j], weight=round(weight, 4), count=int(count))

    isolates = list(nx.isolates(graph))
    graph.remove_nodes_from(isolates)
    return graph


def graph_to_tables(graph: nx.Graph) -> tuple[list[dict], list[dict]]:
    nodes = [
        {
            "term": node,
            "label": data.get("label", node),
            "frequency": data.get("frequency", 0),
            "community": data.get("community", -1),
        }
        for node, data in graph.nodes(data=True)
    ]
    edges = [
        {
            "source": source,
            "target": target,
            "weight": data.get("weight", 0),
            "count": data.get("count", 0),
        }
        for source, target, data in graph.edges(data=True)
    ]
    return nodes, edges
