"""Incident traceability helpers for terms and co-occurring term pairs."""

from __future__ import annotations

import pandas as pd


def incidents_for_term(term: str, term_ticket_ids: dict[str, set[str]], frame: pd.DataFrame) -> pd.DataFrame:
    ids = sorted(term_ticket_ids.get(term, set()))
    return _incident_rows(ids, frame)


def incidents_for_edge(
    source: str, target: str, ticket_terms: dict[str, set[str]], frame: pd.DataFrame
) -> pd.DataFrame:
    ids = sorted(
        ticket_id
        for ticket_id, terms in ticket_terms.items()
        if source in terms and target in terms
    )
    return _incident_rows(ids, frame)


def _incident_rows(ticket_ids: list[str], frame: pd.DataFrame) -> pd.DataFrame:
    if not ticket_ids or "ticket_id" not in frame.columns:
        return pd.DataFrame()
    columns = [
        col
        for col in [
            "ticket_id",
            "short_description",
            "business_unit",
            "country",
            "state",
            "location",
            "category",
            "assignment_group",
            "priority",
            "status",
            "opened_at",
        ]
        if col in frame.columns
    ]
    rows = frame[frame["ticket_id"].astype(str).isin(ticket_ids)][columns].copy()
    order = {ticket_id: idx for idx, ticket_id in enumerate(ticket_ids)}
    rows["_sort"] = rows["ticket_id"].astype(str).map(order)
    return rows.sort_values("_sort").drop(columns=["_sort"])


def add_ticket_links(frame: pd.DataFrame, template: str) -> pd.DataFrame:
    if frame.empty or "ticket_id" not in frame.columns:
        return frame
    out = frame.copy()
    out["ticket_url"] = out["ticket_id"].astype(str).map(
        lambda ticket_id: template.format(ticket_id=ticket_id)
    )
    return out
