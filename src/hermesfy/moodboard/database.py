"""Moodboard Database — SQLite storage layer.

Persistencia estructurada de moodboards con IDs tipo mb_a1b2c3d4.
Soporta creación, búsqueda, recuperación y reuso de moodboards.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("hermesfy.moodboard.database")

MOODBOARD_DIR = Path.home() / ".hermesfy" / "moodboard"
DB_PATH = MOODBOARD_DIR / "moodboards.db"
IMAGES_DIR = MOODBOARD_DIR / "images"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS moodboards (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT,

    concept     TEXT NOT NULL,
    source      TEXT NOT NULL,
    source_url  TEXT,

    format      TEXT DEFAULT 'default',
    brand       TEXT,

    status      TEXT DEFAULT 'created',
    error_msg   TEXT,

    image_count     INTEGER DEFAULT 0,
    images_path     TEXT,
    source_data     TEXT,
    mood_spec       TEXT,
    mood_spec_md    TEXT,

    tags            TEXT,
    used_in_generations INTEGER DEFAULT 0,
    last_used_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_mb_concept ON moodboards(concept);
CREATE INDEX IF NOT EXISTS idx_mb_brand ON moodboards(brand);
CREATE INDEX IF NOT EXISTS idx_mb_created ON moodboards(created_at);
CREATE INDEX IF NOT EXISTS idx_mb_status ON moodboards(status);
"""


class MoodboardDB:
    """SQLite-backed moodboard persistence."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.debug("Moodboard DB ready at %s", self.db_path)

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ── ID generation ─────────────────────────────────────────────────

    @staticmethod
    def _generate_id() -> str:
        """Genera IDs tipo mb_a1b2c3d4."""
        suffix = secrets.token_hex(4)
        return f"mb_{suffix}"

    # ── CRUD ───────────────────────────────────────────────────────────

    def create_moodboard(
        self,
        concept: str,
        source: str = "pinterest_board",
        source_url: str | None = None,
        format: str = "default",
        brand: str | None = None,
        tags: str | None = None,
    ) -> str:
        """Crea un moodboard y devuelve su ID."""
        mb_id = self._generate_id()
        now = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO moodboards
                   (id, created_at, updated_at, concept, source, source_url,
                    format, brand, status, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'created', ?)""",
                (mb_id, now, now, concept, source, source_url,
                 format, brand, tags),
            )
        logger.info("Moodboard %s created: concept='%s' source=%s", mb_id, concept, source)
        return mb_id

    def get_moodboard(self, mb_id: str) -> dict | None:
        """Recupera un moodboard completo."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM moodboards WHERE id = ?", (mb_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def update_moodboard(self, mb_id: str, **kwargs):
        """Actualiza campos de un moodboard."""
        columns = {
            "concept": "concept",
            "source": "source",
            "source_url": "source_url",
            "format": "format",
            "brand": "brand",
            "status": "status",
            "error_msg": "error_msg",
            "image_count": "image_count",
            "images_path": "images_path",
            "source_data": "source_data",
            "mood_spec": "mood_spec",
            "mood_spec_md": "mood_spec_md",
            "tags": "tags",
            "used_in_generations": "used_in_generations",
            "last_used_at": "last_used_at",
            "updated_at": "updated_at",
        }
        filtered = {k: v for k, v in kwargs.items() if k in columns}
        if not filtered:
            return

        filtered["updated_at"] = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            for key, value in filtered.items():
                column = columns[key]
                conn.execute(f"UPDATE moodboards SET {column} = ? WHERE id = ?", (value, mb_id))

    def mark_used(self, mb_id: str):
        """Incrementa contador de usos."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """UPDATE moodboards SET used_in_generations = used_in_generations + 1,
                   last_used_at = ? WHERE id = ?""",
                (now, mb_id),
            )

    def delete_moodboard(self, mb_id: str):
        """Elimina un moodboard (solo DB, no las imágenes)."""
        with self._conn() as conn:
            conn.execute("DELETE FROM moodboards WHERE id = ?", (mb_id,))

    # ── List / Search ─────────────────────────────────────────────────

    def list_moodboards(
        self,
        limit: int = 20,
        offset: int = 0,
        brand: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Lista moodboards con filtros opcionales."""
        query = "SELECT * FROM moodboards"
        params: list[Any] = []
        clauses: list[str] = []

        if brand:
            clauses.append("brand = ?")
            params.append(brand)
        if status:
            clauses.append("status = ?")
            params.append(status)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def search_moodboards(self, query: str, limit: int = 10) -> list[dict]:
        """Busca moodboards por concepto o tags."""
        like = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM moodboards
                   WHERE concept LIKE ? OR tags LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (like, like, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Stats ──────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Estadísticas generales."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM moodboards").fetchone()[0]
            brands = conn.execute(
                "SELECT COUNT(DISTINCT brand) FROM moodboards WHERE brand IS NOT NULL"
            ).fetchone()[0]
            avg = conn.execute(
                "SELECT AVG(image_count) FROM moodboards WHERE image_count > 0"
            ).fetchone()[0] or 0
            by_status = conn.execute(
                "SELECT status, COUNT(*) FROM moodboards GROUP BY status"
            ).fetchall()
        return {
            "total_moodboards": total,
            "total_brands": brands,
            "avg_images": round(avg, 1),
            "by_status": {r[0]: r[1] for r in by_status},
        }

    def get_images_path(self, mb_id: str) -> Path:
        """Devuelve la carpeta de imágenes para un moodboard."""
        p = MOODBOARD_DIR / "images" / mb_id
        p.mkdir(parents=True, exist_ok=True)
        return p
