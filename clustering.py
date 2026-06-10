"""Community detection for ticket term graphs."""

from __future__ import annotations

from collections import defaultdict

import networkx as nx


def apply_communities(graph: nx.Graph, resolution: float = 1.0, seed: int = 42) -> nx.Graph:
    if graph.number_of_nodes() == 0:
        return graph
    try:
        import community as community_louvain

        partition = community_louvain.best_partition(
            graph, weight="weight", resolution=resolution, random_state=seed
        )
    except Exception:
        communities = nx.algorithms.community.greedy_modularity_communities(graph, weight="weight")
        partition = {
            node: idx for idx, community_nodes in enumerate(communities) for node in community_nodes
        }
    nx.set_node_attributes(graph, partition, "community")
    return graph


def cluster_terms(graph: nx.Graph) -> dict[int, list[str]]:
    clusters: dict[int, list[str]] = defaultdict(list)
    for node, data in graph.nodes(data=True):
        clusters[int(data.get("community", -1))].append(node)
    return {
        cid: sorted(terms, key=lambda term: (-graph.nodes[term].get("frequency", 0), term))
        for cid, terms in sorted(clusters.items())
    }
