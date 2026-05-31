from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import CommunityExcerpt, CommunityStatsResponse, ConversationState, PlayerCaseState


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS player_case_states (
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    suspicion_level INTEGER NOT NULL,
    unlocked_document_ids JSONB NOT NULL,
    unlocked_suspect_ids JSONB NOT NULL,
    pinned_evidence_ids JSONB NOT NULL,
    board_links JSONB NOT NULL,
    rescan_history JSONB NOT NULL,
    discovered_contexts JSONB NOT NULL,
    current_objective TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (case_id, player_alias)
);

CREATE TABLE IF NOT EXISTS conversation_states (
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    suspect_id TEXT NOT NULL,
    trust INTEGER NOT NULL,
    guardedness INTEGER NOT NULL,
    revealed_fact_ids JSONB NOT NULL,
    confronted_evidence_ids JSONB NOT NULL,
    memory_summary TEXT NOT NULL,
    transcript JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (case_id, player_alias, suspect_id)
);

CREATE TABLE IF NOT EXISTS theory_submissions (
    id BIGSERIAL PRIMARY KEY,
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    culprit_id TEXT NOT NULL,
    motive_text TEXT NOT NULL,
    timeline_text TEXT NOT NULL,
    evidence_ids JSONB NOT NULL,
    excerpt TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS player_case_states (
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    suspicion_level INTEGER NOT NULL,
    unlocked_document_ids TEXT NOT NULL,
    unlocked_suspect_ids TEXT NOT NULL,
    pinned_evidence_ids TEXT NOT NULL,
    board_links TEXT NOT NULL,
    rescan_history TEXT NOT NULL,
    discovered_contexts TEXT NOT NULL,
    current_objective TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, player_alias)
);

CREATE TABLE IF NOT EXISTS conversation_states (
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    suspect_id TEXT NOT NULL,
    trust INTEGER NOT NULL,
    guardedness INTEGER NOT NULL,
    revealed_fact_ids TEXT NOT NULL,
    confronted_evidence_ids TEXT NOT NULL,
    memory_summary TEXT NOT NULL,
    transcript TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, player_alias, suspect_id)
);

CREATE TABLE IF NOT EXISTS theory_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    culprit_id TEXT NOT NULL,
    motive_text TEXT NOT NULL,
    timeline_text TEXT NOT NULL,
    evidence_ids TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _dump_json(value: Any) -> str:
    return json.dumps(value)


def _load_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _row_value(row: Any, key: str) -> Any:
    return row[key]


def _state_from_row(player_alias: str, case_id: str, row: Any) -> PlayerCaseState:
    return PlayerCaseState(
        player_alias=player_alias,
        case_id=case_id,
        suspicion_level=_row_value(row, "suspicion_level"),
        unlocked_document_ids=_load_json(_row_value(row, "unlocked_document_ids")),
        unlocked_suspect_ids=_load_json(_row_value(row, "unlocked_suspect_ids")),
        pinned_evidence_ids=_load_json(_row_value(row, "pinned_evidence_ids")),
        board_links=_load_json(_row_value(row, "board_links")),
        rescan_history=_load_json(_row_value(row, "rescan_history")),
        discovered_contexts=_load_json(_row_value(row, "discovered_contexts")),
        current_objective=_row_value(row, "current_objective"),
    )


def _conversation_from_row(row: Any) -> ConversationState:
    return ConversationState(
        suspect_id=_row_value(row, "suspect_id"),
        trust=_row_value(row, "trust"),
        guardedness=_row_value(row, "guardedness"),
        revealed_fact_ids=_load_json(_row_value(row, "revealed_fact_ids")),
        confronted_evidence_ids=_load_json(_row_value(row, "confronted_evidence_ids")),
        memory_summary=_row_value(row, "memory_summary"),
        transcript=_load_json(_row_value(row, "transcript")),
    )


class BaseDatabase(ABC):
    """Shared implementation of all persistence operations.

    Subclasses implement _execute, _execute_write, and _init_schema to provide
    the DB-specific connection and DDL; all business logic lives here.
    """

    @abstractmethod
    def _execute(self, sql: str, params: tuple = ()) -> list[Any]:
        """Run a SELECT and return all rows as dicts."""

    @abstractmethod
    def _execute_write(self, sql: str, params: tuple = ()) -> None:
        """Run an INSERT/UPDATE/DELETE."""

    @abstractmethod
    def _init_schema(self) -> None:
        """Create tables if they do not exist."""

    # ------------------------------------------------------------------ #
    # Player state                                                         #
    # ------------------------------------------------------------------ #

    def load_player_state(self, case_id: str, player_alias: str) -> PlayerCaseState | None:
        rows = self._execute(
            "SELECT * FROM player_case_states WHERE case_id = {p} AND player_alias = {p}".format(p=self._ph),
            (case_id, player_alias),
        )
        if not rows:
            return None
        return _state_from_row(player_alias, case_id, rows[0])

    def save_player_state(self, state: PlayerCaseState) -> None:
        p = self._ph
        self._execute_write(
            f"""
            INSERT INTO player_case_states (
                case_id, player_alias, suspicion_level, unlocked_document_ids,
                unlocked_suspect_ids, pinned_evidence_ids, board_links,
                rescan_history, discovered_contexts, current_objective
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT(case_id, player_alias) DO UPDATE SET
                suspicion_level = {self._excluded}suspicion_level,
                unlocked_document_ids = {self._excluded}unlocked_document_ids,
                unlocked_suspect_ids = {self._excluded}unlocked_suspect_ids,
                pinned_evidence_ids = {self._excluded}pinned_evidence_ids,
                board_links = {self._excluded}board_links,
                rescan_history = {self._excluded}rescan_history,
                discovered_contexts = {self._excluded}discovered_contexts,
                current_objective = {self._excluded}current_objective,
                updated_at = {self._now}
            """,
            (
                state.case_id,
                state.player_alias,
                state.suspicion_level,
                self._json(state.unlocked_document_ids),
                self._json(state.unlocked_suspect_ids),
                self._json(state.pinned_evidence_ids),
                self._json(state.board_links),
                self._json(state.rescan_history),
                self._json(state.discovered_contexts),
                state.current_objective,
            ),
        )

    # ------------------------------------------------------------------ #
    # Conversations                                                        #
    # ------------------------------------------------------------------ #

    def load_conversations(self, case_id: str, player_alias: str) -> list[ConversationState]:
        rows = self._execute(
            "SELECT * FROM conversation_states WHERE case_id = {p} AND player_alias = {p} ORDER BY suspect_id".format(p=self._ph),
            (case_id, player_alias),
        )
        return [_conversation_from_row(row) for row in rows]

    def load_conversation(self, case_id: str, player_alias: str, suspect_id: str) -> ConversationState | None:
        p = self._ph
        rows = self._execute(
            f"SELECT * FROM conversation_states WHERE case_id = {p} AND player_alias = {p} AND suspect_id = {p}",
            (case_id, player_alias, suspect_id),
        )
        if not rows:
            return None
        return _conversation_from_row(rows[0])

    def save_conversation(self, case_id: str, player_alias: str, conversation: ConversationState) -> None:
        p = self._ph
        self._execute_write(
            f"""
            INSERT INTO conversation_states (
                case_id, player_alias, suspect_id, trust, guardedness,
                revealed_fact_ids, confronted_evidence_ids, memory_summary, transcript
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT(case_id, player_alias, suspect_id) DO UPDATE SET
                trust = {self._excluded}trust,
                guardedness = {self._excluded}guardedness,
                revealed_fact_ids = {self._excluded}revealed_fact_ids,
                confronted_evidence_ids = {self._excluded}confronted_evidence_ids,
                memory_summary = {self._excluded}memory_summary,
                transcript = {self._excluded}transcript,
                updated_at = {self._now}
            """,
            (
                case_id,
                player_alias,
                conversation.suspect_id,
                conversation.trust,
                conversation.guardedness,
                self._json(conversation.revealed_fact_ids),
                self._json(conversation.confronted_evidence_ids),
                conversation.memory_summary,
                self._json([turn.model_dump() for turn in conversation.transcript]),
            ),
        )

    # ------------------------------------------------------------------ #
    # Theory submissions                                                   #
    # ------------------------------------------------------------------ #

    def save_submission(
        self,
        case_id: str,
        player_alias: str,
        culprit_id: str,
        motive_text: str,
        timeline_text: str,
        evidence_ids: list[str],
        excerpt: str,
    ) -> None:
        p = self._ph
        self._execute_write(
            f"""
            INSERT INTO theory_submissions (
                case_id, player_alias, culprit_id, motive_text, timeline_text, evidence_ids, excerpt
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            (case_id, player_alias, culprit_id, motive_text, timeline_text, self._json(evidence_ids), excerpt),
        )

    def get_community_stats(self, case_id: str) -> CommunityStatsResponse:
        rows = self._execute(
            "SELECT player_alias, culprit_id, evidence_ids, excerpt FROM theory_submissions WHERE case_id = {p} ORDER BY created_at".format(p=self._ph),
            (case_id,),
        )
        culprit_counts: dict[str, int] = {}
        evidence_counts: dict[str, int] = {}
        excerpts: list[CommunityExcerpt] = []
        for row in rows:
            culprit_counts[row["culprit_id"]] = culprit_counts.get(row["culprit_id"], 0) + 1
            for evidence_id in _load_json(row["evidence_ids"]):
                evidence_counts[evidence_id] = evidence_counts.get(evidence_id, 0) + 1
            excerpts.append(CommunityExcerpt(player_alias=row["player_alias"], excerpt=row["excerpt"]))
        return CommunityStatsResponse(
            case_id=case_id,
            culprit_counts=culprit_counts,
            evidence_counts=evidence_counts,
            excerpts=excerpts[-5:],
        )

    # ------------------------------------------------------------------ #
    # Subclass hooks — override these, not the methods above              #
    # ------------------------------------------------------------------ #

    @property
    def _ph(self) -> str:
        """SQL parameter placeholder."""
        return "?"

    @property
    def _excluded(self) -> str:
        """Prefix for UPSERT excluded values."""
        return "excluded."

    @property
    def _now(self) -> str:
        """SQL expression for current timestamp."""
        return "CURRENT_TIMESTAMP"

    def _json(self, value: Any) -> Any:
        """Serialise a value for storage."""
        return _dump_json(value)


class SQLiteDatabase(BaseDatabase):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self._connection() as connection:
            connection.executescript(SQLITE_SCHEMA)

    def _execute(self, sql: str, params: tuple = ()) -> list[Any]:
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _execute_write(self, sql: str, params: tuple = ()) -> None:
        with self._connection() as connection:
            connection.execute(sql, params)


class PostgresDatabase(BaseDatabase):
    def __init__(self, database_url: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL support requires psycopg. Install backend requirements first."
            ) from exc

        self.psycopg = psycopg
        self.dict_row = dict_row
        self.Jsonb = Jsonb
        self.database_url = database_url
        self._init_schema()

    def _connect(self):
        return self.psycopg.connect(self.database_url, row_factory=self.dict_row)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self._connect() as connection:
            yield connection

    def _init_schema(self) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_SCHEMA)

    def _execute(self, sql: str, params: tuple = ()) -> list[Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()

    def _execute_write(self, sql: str, params: tuple = ()) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)

    @property
    def _ph(self) -> str:
        return "%s"

    @property
    def _excluded(self) -> str:
        return "EXCLUDED."

    @property
    def _now(self) -> str:
        return "NOW()"

    def _json(self, value: Any) -> Any:
        # Pass a Jsonb wrapper so psycopg3 serialises it without needing ::jsonb casts in SQL
        return self.Jsonb(value)


def create_database(database_url: str | None, db_path: Path) -> BaseDatabase:
    if database_url:
        return PostgresDatabase(database_url)
    return SQLiteDatabase(db_path)
