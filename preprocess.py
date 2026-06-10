"""Ticket text cleaning, tokenization, normalization, and phrase handling."""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from typing import Iterable

import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from config import PipelineConfig, REQUIRED_COLUMNS, TEXT_COLUMNS


TOKEN_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)?")
HTML_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
TIMESTAMP_RE = re.compile(
    r"\b\d{1,2}[:/.-]\d{1,2}(?:[:/.-]\d{2,4})?(?:\s?[ap]m)?\b", re.I
)
INCIDENT_RE = re.compile(r"\b(?:inc|req|ritm|chg|task)\d+\b", re.I)
PHRASE_BLOCKLIST = {
    "add",
    "apply",
    "authenticate",
    "caus",
    "check",
    "clear",
    "confirm",
    "connect",
    "disable",
    "enable",
    "fail",
    "flush",
    "install",
    "map",
    "move",
    "push",
    "ran",
    "reapply",
    "rebuild",
    "reconnect",
    "release",
    "renew",
    "replace",
    "reset",
    "restart",
    "restore",
    "run",
    "set",
    "swap",
    "test",
    "update",
    "verify",
}


@dataclass
class ProcessedTickets:
    frame: pd.DataFrame
    documents: list[list[str]]
    ticket_terms: dict[str, set[str]]
    term_ticket_ids: dict[str, set[str]]
    warnings: list[str]


def normalize_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Rename columns case-insensitively to expected canonical names when possible."""
    warnings: list[str] = []
    canonical = {
        "ticket_id",
        "opened_at",
        "category",
        "subcategory",
        "assignment_group",
        "priority",
        "short_description",
        "work_notes",
        "close_notes",
        "status",
        "business_unit",
        "location",
        "country",
        "state",
    }
    rename: dict[str, str] = {}
    seen_lower: dict[str, str] = {}
    for col in frame.columns:
        key = str(col).strip().lower()
        seen_lower[key] = col
        if key in canonical and col != key:
            rename[col] = key
    frame = frame.rename(columns=rename)

    for required in REQUIRED_COLUMNS:
        if required not in frame.columns:
            warnings.append(f"Required column '{required}' is missing.")
    missing_text = [col for col in TEXT_COLUMNS if col not in frame.columns]
    if missing_text:
        warnings.append("Text column(s) missing: " + ", ".join(missing_text))
    if "ticket_id" not in frame.columns:
        frame["ticket_id"] = [f"ROW{i + 1:06d}" for i in range(len(frame))]
    frame["ticket_id"] = frame["ticket_id"].fillna("").astype(str).str.strip()
    blanks = frame["ticket_id"].eq("")
    if blanks.any():
        frame.loc[blanks, "ticket_id"] = [f"ROW{i + 1:06d}" for i in frame.index[blanks]]
        warnings.append("Blank ticket_id values were replaced with ROW ids.")
    return frame, warnings


def read_ticket_csvs(files: Iterable) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    warnings: list[str] = []
    for file in files:
        try:
            frames.append(pd.read_csv(file, dtype=str, keep_default_na=False))
        except UnicodeDecodeError:
            frames.append(pd.read_csv(file, dtype=str, keep_default_na=False, encoding="latin-1"))
    if not frames:
        return pd.DataFrame(), ["No CSV files were loaded."]
    frame = pd.concat(frames, ignore_index=True)
    frame, column_warnings = normalize_columns(frame)
    warnings.extend(column_warnings)
    return frame, warnings


def parse_stopwords(text: str) -> set[str]:
    words = re.split(r"[\s,]+", text.strip().lower())
    return {word for word in words if word}


def parse_synonyms(text: str) -> dict[str, str]:
    if not text.strip():
        return {}
    try:
        raw = json.loads(text)
        return {str(k).lower().strip(): str(v).lower().strip() for k, v in raw.items()}
    except json.JSONDecodeError:
        pairs: dict[str, str] = {}
        for line in text.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
            elif ":" in line:
                key, value = line.split(":", 1)
            else:
                continue
            pairs[key.strip().lower()] = value.strip().lower()
        return pairs


def clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = html.unescape(text).lower()
    text = HTML_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)
    text = TIMESTAMP_RE.sub(" ", text)
    text = INCIDENT_RE.sub(" ", text)
    text = text.replace("_", " ")
    return text


def simple_lemma(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


@lru_cache(maxsize=1)
def get_spacy_nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm", disable=["parser", "ner"])
    except Exception:
        return None


def normalize_tokens(tokens: list[str]) -> list[str]:
    nlp = get_spacy_nlp()
    if nlp is None:
        return [simple_lemma(token) for token in tokens]
    doc = nlp(" ".join(token.replace("_", " ") for token in tokens))
    return [token.lemma_.lower().strip() or token.text.lower() for token in doc]


def tokenize(text: str, stopwords: set[str], synonyms: dict[str, str]) -> list[str]:
    stop = set(ENGLISH_STOP_WORDS) | stopwords
    expanded: list[str] = []
    for token in TOKEN_RE.findall(clean_text(text)):
        if token.isdigit() or token in stop:
            continue
        token = synonyms.get(token, token)
        replacement = token.replace(" ", "_")
        for part in replacement.split():
            expanded.append(part)
    out: list[str] = []
    for term in normalize_tokens(expanded):
        term = term.replace(" ", "_")
        if len(term) > 1 and term not in stop and not term.isdigit():
            out.append(term)
    return out


def assemble_documents(
    frame: pd.DataFrame, text_columns: list[str], config: PipelineConfig
) -> list[list[str]]:
    docs: list[list[str]] = []
    available = [col for col in text_columns if col in frame.columns]
    for _, row in frame.iterrows():
        raw = " ".join(str(row.get(col, "") or "") for col in available)
        docs.append(tokenize(raw, config.stopwords, config.synonyms))
    return docs


def _phrase_tuple(term: str) -> tuple[str, ...]:
    return tuple(term.lower().replace("_", " ").split())


def learn_phrases(
    documents: list[list[str]], known_phrases: set[str], min_count: int
) -> set[tuple[str, ...]]:
    counts: Counter[tuple[str, ...]] = Counter()
    known = {_phrase_tuple(phrase) for phrase in known_phrases}
    for doc in documents:
        words = [token.replace("_", " ") for token in doc]
        flat = list(chain.from_iterable(word.split() for word in words))
        for n in (2, 3):
            for i in range(max(0, len(flat) - n + 1)):
                gram = tuple(flat[i : i + n])
                counts[gram] += 1
    learned = {
        gram
        for gram, count in counts.items()
        if count >= max(8, min_count)
        and not (set(gram) & PHRASE_BLOCKLIST)
        and len(set(gram)) == len(gram)
        and any("_".join(gram).startswith("_".join(known_phrase)) for known_phrase in known)
    }
    return known | learned


def apply_phrases(
    documents: list[list[str]], phrases: set[tuple[str, ...]]
) -> list[list[str]]:
    if not phrases:
        return documents
    by_first: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    for phrase in sorted(phrases, key=len, reverse=True):
        by_first[phrase[0]].append(phrase)

    merged_docs: list[list[str]] = []
    for doc in documents:
        flat = list(chain.from_iterable(token.replace("_", " ").split() for token in doc))
        merged: list[str] = []
        i = 0
        while i < len(flat):
            match = None
            for phrase in by_first.get(flat[i], []):
                if tuple(flat[i : i + len(phrase)]) == phrase:
                    match = phrase
                    break
            if match:
                merged.append("_".join(match))
                i += len(match)
            else:
                merged.append(flat[i])
                i += 1
        merged_docs.append(merged)
    return merged_docs


def process_tickets(
    frame: pd.DataFrame, text_columns: list[str], config: PipelineConfig
) -> ProcessedTickets:
    frame, warnings = normalize_columns(frame.copy())
    documents = assemble_documents(frame, text_columns, config)
    if config.phrase_detection:
        phrases = learn_phrases(documents, config.known_phrases, config.phrase_min_count)
        documents = apply_phrases(documents, phrases)

    ticket_terms: dict[str, set[str]] = {}
    term_ticket_ids: dict[str, set[str]] = defaultdict(set)
    for ticket_id, terms in zip(frame["ticket_id"].astype(str), documents, strict=False):
        unique_terms = set(terms)
        ticket_terms[ticket_id] = unique_terms
        for term in unique_terms:
            term_ticket_ids[term].add(ticket_id)
    return ProcessedTickets(frame, documents, ticket_terms, dict(term_ticket_ids), warnings)
