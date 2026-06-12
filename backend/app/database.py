from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import AuthoringBundle, AuthUserRecord, CommunityExcerpt, CommunityStatsResponse, ConversationState, PlayerCaseState, SessionRecord


POSTGRES_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS player_case_states (
    case_id TEXT NOT NULL,
    player_alias TEXT NOT NULL,
    suspicion_level INTEGER NOT NULL,
    unlocked_document_ids JSONB NOT NULL,
    unlocked_suspect_ids JSONB NOT NULL,
    pinned_evidence_ids JSONB NOT NULL,
    board_links JSONB NOT NULL,
    completed_deduction_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
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

CREATE TABLE IF NOT EXISTS auth_users (
    id TEXT UNIQUE NOT NULL,
    alias TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    role TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rate_limit_events (
    bucket TEXT NOT NULL,
    subject TEXT NOT NULL,
    occurred_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_limit_events_lookup ON rate_limit_events(bucket, subject, occurred_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_alias TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_assets (
    case_id TEXT NOT NULL,
    path TEXT NOT NULL,
    public_url TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (case_id, path)
);

CREATE TABLE IF NOT EXISTS production_cases (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    status TEXT NOT NULL,
    owner_alias TEXT,
    version INTEGER NOT NULL,
    bundle JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_versions (
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    bundle JSONB NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (case_id, version)
);

CREATE TABLE IF NOT EXISTS case_documents (
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    entity_tags JSONB NOT NULL,
    PRIMARY KEY (case_id, version, document_id)
);

CREATE TABLE IF NOT EXISTS retrieval_chunks (
    chunk_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(768)
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
    completed_deduction_ids TEXT NOT NULL DEFAULT '[]',
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

CREATE TABLE IF NOT EXISTS auth_users (
    id TEXT UNIQUE NOT NULL,
    alias TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'player',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    role TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rate_limit_events (
    bucket TEXT NOT NULL,
    subject TEXT NOT NULL,
    occurred_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_limit_events_lookup ON rate_limit_events(bucket, subject, occurred_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_alias TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_assets (
    case_id TEXT NOT NULL,
    path TEXT NOT NULL,
    public_url TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, path)
);

CREATE TABLE IF NOT EXISTS production_cases (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    status TEXT NOT NULL,
    owner_alias TEXT,
    version INTEGER NOT NULL,
    bundle TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_versions (
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    bundle TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, version)
);

CREATE TABLE IF NOT EXISTS case_documents (
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    entity_tags TEXT NOT NULL,
    PRIMARY KEY (case_id, version, document_id)
);

CREATE TABLE IF NOT EXISTS retrieval_chunks (
    chunk_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding TEXT
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


def _row_value_or(row: Any, key: str, default: Any) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def _state_from_row(player_alias: str, case_id: str, row: Any) -> PlayerCaseState:
    return PlayerCaseState(
        player_alias=player_alias,
        case_id=case_id,
        suspicion_level=_row_value(row, "suspicion_level"),
        unlocked_document_ids=_load_json(_row_value(row, "unlocked_document_ids")),
        unlocked_suspect_ids=_load_json(_row_value(row, "unlocked_suspect_ids")),
        pinned_evidence_ids=_load_json(_row_value(row, "pinned_evidence_ids")),
        board_links=_load_json(_row_value(row, "board_links")),
        completed_deduction_ids=_load_json(_row_value_or(row, "completed_deduction_ids", "[]")),
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
                completed_deduction_ids, rescan_history, discovered_contexts,
                current_objective
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT(case_id, player_alias) DO UPDATE SET
                suspicion_level = {self._excluded}suspicion_level,
                unlocked_document_ids = {self._excluded}unlocked_document_ids,
                unlocked_suspect_ids = {self._excluded}unlocked_suspect_ids,
                pinned_evidence_ids = {self._excluded}pinned_evidence_ids,
                board_links = {self._excluded}board_links,
                completed_deduction_ids = {self._excluded}completed_deduction_ids,
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
                self._json(state.completed_deduction_ids),
                self._json(state.rescan_history),
                self._json(state.discovered_contexts),
                state.current_objective,
            ),
        )

    def delete_player_state(self, case_id: str, player_alias: str) -> None:
        self._execute_write(
            "DELETE FROM player_case_states WHERE case_id = {p} AND player_alias = {p}".format(p=self._ph),
            (case_id, player_alias),
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

    def delete_conversations(self, case_id: str, player_alias: str) -> None:
        self._execute_write(
            "DELETE FROM conversation_states WHERE case_id = {p} AND player_alias = {p}".format(p=self._ph),
            (case_id, player_alias),
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
    # Auth users                                                           #
    # ------------------------------------------------------------------ #

    def load_auth_user(self, alias: str) -> AuthUserRecord | None:
        rows = self._execute(
            "SELECT id, alias, password_hash, role FROM auth_users WHERE alias = {p}".format(p=self._ph),
            (alias,),
        )
        if not rows:
            return None
        row = rows[0]
        return AuthUserRecord(
            id=_row_value(row, "id"),
            alias=_row_value(row, "alias"),
            password_hash=_row_value(row, "password_hash"),
            role=_row_value(row, "role"),
        )

    def create_auth_user(self, user: AuthUserRecord) -> None:
        p = self._ph
        self._execute_write(
            f"INSERT INTO auth_users (id, alias, password_hash, role) VALUES ({p}, {p}, {p}, {p})",
            (user.id, user.alias, user.password_hash, user.role),
        )

    def update_auth_password(self, alias: str, password_hash: str) -> None:
        self._execute_write(
            "UPDATE auth_users SET password_hash = {p} WHERE alias = {p}".format(p=self._ph),
            (password_hash, alias),
        )

    def create_session(self, session: SessionRecord) -> None:
        p = self._ph
        self._execute_write(
            f"INSERT INTO auth_sessions (token_hash, user_id, alias, role, expires_at) VALUES ({p}, {p}, {p}, {p}, {p})",
            (session.token_hash, session.user_id, session.alias, session.role, session.expires_at),
        )

    def load_session(self, token_hash: str, now_epoch: int) -> SessionRecord | None:
        p = self._ph
        rows = self._execute(
            f"SELECT token_hash, user_id, alias, role, expires_at FROM auth_sessions WHERE token_hash = {p} AND expires_at > {p}",
            (token_hash, now_epoch),
        )
        if not rows:
            return None
        return SessionRecord.model_validate(rows[0])

    def revoke_session(self, token_hash: str) -> None:
        self._execute_write("DELETE FROM auth_sessions WHERE token_hash = {p}".format(p=self._ph), (token_hash,))

    def consume_rate_limit(self, bucket: str, subject: str, limit: int, window_seconds: int, now_epoch: int) -> bool:
        p = self._ph
        cutoff = now_epoch - window_seconds
        self._execute_write(
            f"DELETE FROM rate_limit_events WHERE bucket = {p} AND subject = {p} AND occurred_at <= {p}",
            (bucket, subject, cutoff),
        )
        rows = self._execute(
            f"SELECT COUNT(*) AS count FROM rate_limit_events WHERE bucket = {p} AND subject = {p} AND occurred_at > {p}",
            (bucket, subject, cutoff),
        )
        if int(rows[0]["count"]) >= limit:
            return False
        self._execute_write(
            f"INSERT INTO rate_limit_events (bucket, subject, occurred_at) VALUES ({p}, {p}, {p})",
            (bucket, subject, now_epoch),
        )
        return True

    def write_audit_log(self, actor_alias: str, action: str, target: str, metadata: dict[str, Any] | None = None) -> None:
        p = self._ph
        self._execute_write(
            f"INSERT INTO audit_logs (actor_alias, action, target, metadata) VALUES ({p}, {p}, {p}, {p})",
            (actor_alias, action, target, self._json(metadata or {})),
        )

    def save_case_asset(self, case_id: str, path: str, public_url: str, content_type: str, size_bytes: int) -> None:
        p = self._ph
        self._execute_write(
            f"""
            INSERT INTO case_assets (case_id, path, public_url, content_type, size_bytes)
            VALUES ({p}, {p}, {p}, {p}, {p})
            ON CONFLICT(case_id, path) DO UPDATE SET
                public_url = {self._excluded}public_url,
                content_type = {self._excluded}content_type,
                size_bytes = {self._excluded}size_bytes
            """,
            (case_id, path, public_url, content_type, size_bytes),
        )

    def list_case_assets(self, case_id: str) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT path, public_url, content_type, size_bytes FROM case_assets WHERE case_id = {p} ORDER BY path".format(p=self._ph),
            (case_id,),
        )

    def save_case_bundle(self, bundle: AuthoringBundle) -> None:
        p = self._ph
        self._execute_write(
            f"""
            INSERT INTO production_cases (id, owner_user_id, status, owner_alias, version, bundle)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT(id) DO UPDATE SET
                owner_user_id = {self._excluded}owner_user_id,
                status = {self._excluded}status,
                owner_alias = {self._excluded}owner_alias,
                version = {self._excluded}version,
                bundle = {self._excluded}bundle,
                updated_at = {self._now}
            """,
            (
                bundle.case.id,
                bundle.case.owner_user_id,
                bundle.case.status,
                bundle.case.owner_alias,
                bundle.case.version,
                self._json(bundle.model_dump(mode="json")),
            ),
        )
        self._execute_write(
            f"""
            INSERT INTO case_versions (case_id, version, bundle, created_by)
            VALUES ({p}, {p}, {p}, {p})
            ON CONFLICT(case_id, version) DO UPDATE SET bundle = {self._excluded}bundle
            """,
            (bundle.case.id, bundle.case.version, self._json(bundle.model_dump(mode="json")), bundle.case.owner_alias or "system"),
        )
        self._execute_write(
            f"DELETE FROM case_documents WHERE case_id = {p} AND version = {p}",
            (bundle.case.id, bundle.case.version),
        )
        for document in bundle.documents:
            self._execute_write(
                f"""
                INSERT INTO case_documents (case_id, version, document_id, title, body, entity_tags)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p})
                """,
                (bundle.case.id, bundle.case.version, document.id, document.title, document.body, self._json(document.entity_tags)),
            )

    def load_case_bundle(self, case_id: str) -> AuthoringBundle | None:
        rows = self._execute(
            "SELECT bundle FROM production_cases WHERE id = {p}".format(p=self._ph),
            (case_id,),
        )
        if not rows:
            return None
        return AuthoringBundle.model_validate(_load_json(rows[0]["bundle"]))

    def list_case_bundles(self) -> list[AuthoringBundle]:
        rows = self._execute("SELECT bundle FROM production_cases ORDER BY id")
        return [AuthoringBundle.model_validate(_load_json(row["bundle"])) for row in rows]

    def delete_case_bundle(self, case_id: str) -> None:
        p = self._ph
        for table in (
            "retrieval_chunks",
            "case_documents",
            "case_versions",
            "case_assets",
            "conversation_states",
            "player_case_states",
            "theory_submissions",
        ):
            self._execute_write(f"DELETE FROM {table} WHERE case_id = {p}", (case_id,))
        self._execute_write(f"DELETE FROM production_cases WHERE id = {p}", (case_id,))

    def replace_retrieval_chunks(
        self,
        case_id: str,
        version: int,
        chunks: list[tuple[str, str, str, str, list[float] | None]],
    ) -> None:
        p = self._ph
        self._execute_write(f"DELETE FROM retrieval_chunks WHERE case_id = {p} AND version = {p}", (case_id, version))
        for chunk_id, document_id, content_hash, text, embedding in chunks:
            self._execute_write(
                f"""
                INSERT INTO retrieval_chunks (chunk_id, case_id, version, document_id, content_hash, text, embedding)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                (chunk_id, case_id, version, document_id, content_hash, text, self._vector(embedding)),
            )

    # ------------------------------------------------------------------ #
    # Subclass hooks — override these, not the methods above              #
    # ------------------------------------------------------------------ #

    @property
    def supports_vector_index(self) -> bool:
        return False

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

    def _vector(self, value: list[float] | None) -> Any:
        return _dump_json(value) if value is not None else None


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
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(player_case_states)").fetchall()
            }
            if "completed_deduction_ids" not in columns:
                connection.execute(
                    "ALTER TABLE player_case_states ADD COLUMN completed_deduction_ids TEXT NOT NULL DEFAULT '[]'"
                )
            auth_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(auth_users)").fetchall()
            }
            if "id" not in auth_columns:
                connection.execute("ALTER TABLE auth_users ADD COLUMN id TEXT")
                connection.execute("UPDATE auth_users SET id = lower(hex(randomblob(16))) WHERE id IS NULL")
            if "role" not in auth_columns:
                connection.execute("ALTER TABLE auth_users ADD COLUMN role TEXT NOT NULL DEFAULT 'player'")

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
                cursor.execute(
                    "ALTER TABLE player_case_states ADD COLUMN IF NOT EXISTS completed_deduction_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
                )
                cursor.execute("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS id TEXT")
                cursor.execute("UPDATE auth_users SET id = md5(alias || created_at::text) WHERE id IS NULL")
                cursor.execute("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'player'")

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
    def supports_vector_index(self) -> bool:
        return True

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

    def _vector(self, value: list[float] | None) -> Any:
        return "[" + ",".join(str(item) for item in value) + "]" if value is not None else None


def create_database(database_url: str | None, db_path: Path) -> BaseDatabase:
    if database_url:
        return PostgresDatabase(database_url)
    return SQLiteDatabase(db_path)
