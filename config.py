"""Default configuration for the IT ticket word network."""

from __future__ import annotations

from dataclasses import dataclass, field


TEXT_COLUMNS = ["short_description", "work_notes", "close_notes"]
FILTER_COLUMNS = [
    "business_unit",
    "country",
    "state",
    "location",
    "category",
    "assignment_group",
    "priority",
    "status",
]
REQUIRED_COLUMNS = ["ticket_id"]

IT_STOPWORDS = {
    "advised",
    "am",
    "call",
    "called",
    "close",
    "closed",
    "closing",
    "contacted",
    "customer",
    "add",
    "apply",
    "authenticate",
    "cause",
    "caused",
    "caus",
    "check",
    "checked",
    "clear",
    "cleared",
    "clean",
    "cleaned",
    "confirm",
    "confirmed",
    "connect",
    "connected",
    "day",
    "disable",
    "disabled",
    "disabl",
    "enable",
    "enabled",
    "eod",
    "fail",
    "failed",
    "fix",
    "fixed",
    "flush",
    "flushed",
    "fyi",
    "good",
    "hello",
    "hi",
    "hour",
    "incident",
    "install",
    "installed",
    "issue",
    "kindly",
    "log",
    "logged",
    "map",
    "mapped",
    "mapp",
    "note",
    "normal",
    "normally",
    "online",
    "opened",
    "output",
    "pm",
    "please",
    "push",
    "pushed",
    "ran",
    "reapply",
    "reapplied",
    "reappli",
    "rebuild",
    "rebuilt",
    "reconnect",
    "reconnected",
    "release",
    "released",
    "renew",
    "renewed",
    "replace",
    "replaced",
    "regard",
    "regards",
    "reported",
    "report",
    "request",
    "requester",
    "reset",
    "resolved",
    "resolution",
    "restore",
    "restored",
    "restor",
    "run",
    "service",
    "set",
    "stable",
    "swap",
    "swapped",
    "team",
    "test",
    "tested",
    "thanks",
    "thank",
    "ticket",
    "today",
    "update",
    "updated",
    "updat",
    "user",
    "verify",
    "verified",
    "verifi",
    "work",
    "working",
    "won",
}

SYNONYMS = {
    "acct": "account",
    "ad": "active directory",
    "config": "configuration",
    "dl": "distribution list",
    "distro": "distribution list",
    "email": "email",
    "emails": "email",
    "m365": "office365",
    "o365": "office365",
    "outlook365": "outlook",
    "pc": "computer",
    "pwd": "password",
    "re-installed": "reinstall",
    "reinstalling": "reinstall",
    "reinstalled": "reinstall",
    "vpn": "vpn",
}

KNOWN_PHRASES = {
    "active directory",
    "blue screen",
    "distribution list",
    "docking station",
    "hard drive",
    "network drive",
    "print queue",
    "shared mailbox",
    "software center",
    "video conference",
}


@dataclass
class PipelineConfig:
    text_columns: list[str] = field(default_factory=lambda: TEXT_COLUMNS.copy())
    stopwords: set[str] = field(default_factory=lambda: IT_STOPWORDS.copy())
    synonyms: dict[str, str] = field(default_factory=lambda: SYNONYMS.copy())
    known_phrases: set[str] = field(default_factory=lambda: KNOWN_PHRASES.copy())
    phrase_detection: bool = True
    phrase_min_count: int = 2
    cooccurrence_scope: str = "document"
    window_size: int = 8
    edge_weighting: str = "count"
    min_term_frequency: int = 3
    min_edge_weight: float = 2.0
    max_nodes: int = 80
    louvain_resolution: float = 1.8
    service_now_url_template: str = (
        "https://servicenow.mycorp.com/incident.do?sysparm_query=number={ticket_id}"
    )
