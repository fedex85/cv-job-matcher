"""Historial local de ofertas ya analizadas, para avisar de repeticiones.

Privacidad: solo se guarda información de la OFERTA (huella, título y nota). Nunca
se guarda el CV ni su contenido. La base de datos es un archivo SQLite local.

Detección de repetidas:
  * exacta: huella SHA-256 del texto normalizado (ignora mayúsculas, acentos y signos);
  * parecida: firma MinHash sobre grupos de 3 palabras (la misma oferta republicada
    con pequeños cambios supera el umbral de similitud).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from src.utils.helpers import fold
from src.utils.logger import get_logger

log = get_logger(__name__)

SIGNATURE_SIZE = 64
SIMILARITY_THRESHOLD = 0.8
_PRIME = (1 << 61) - 1
_rng = random.Random(20261020)  # semillas fijas: la firma es reproducible entre ejecuciones
_COEFFS = [(_rng.randrange(1, _PRIME), _rng.randrange(0, _PRIME)) for _ in range(SIGNATURE_SIZE)]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    times INTEGER NOT NULL DEFAULT 1,
    last_score REAL NOT NULL,
    last_band TEXT NOT NULL,
    signature TEXT NOT NULL
)
"""


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", fold(text))


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(normalize(text)).encode()).hexdigest()[:16]


def minhash(text: str) -> list[int]:
    words = normalize(text)
    grams = [" ".join(words[i:i + 3]) for i in range(max(1, len(words) - 2))] or [""]
    hashed = {int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big") for g in grams}
    return [min((a * x + b) % _PRIME for x in hashed) for a, b in _COEFFS]


def similarity(sig_a: list[int], sig_b: list[int]) -> float:
    return sum(1 for a, b in zip(sig_a, sig_b, strict=False) if a == b) / SIGNATURE_SIZE


def extract_title(text: str, max_len: int = 90) -> str:
    for line in text.split("\n"):
        line = re.sub(r"^[\s\-*•#]+", "", line).strip()
        if len(line) >= 4:
            return line[:max_len]
    return text.strip()[:max_len] or "(sin título)"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class JobHistory:
    """Con ``db_path=None`` el historial queda desactivado y todas las operaciones son inocuas."""

    def __init__(self, db_path: Path | str | None, max_entries: int = 2000) -> None:
        self.db_path = Path(db_path) if db_path else None
        self.max_entries = max_entries
        self._lock = threading.Lock()
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as con, con:
                con.execute(_SCHEMA)

    @property
    def enabled(self) -> bool:
        return self.db_path is not None

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path, timeout=10)  # type: ignore[arg-type]
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _info(row: sqlite3.Row, exact: bool, sim: float) -> dict:
        return {"id": row["id"], "title": row["title"], "first_seen": row["first_seen"],
                "last_seen": row["last_seen"], "times": row["times"], "last_score": row["last_score"],
                "last_band": row["last_band"], "exact": exact, "similarity": round(sim, 2)}

    def lookup(self, job_text: str) -> dict | None:
        """Devuelve la oferta ya vista (exacta o muy parecida) sin modificar nada."""
        if not self.enabled:
            return None
        job_id, sig = fingerprint(job_text), minhash(job_text)
        with closing(self._connect()) as con:
            row = con.execute("SELECT * FROM seen_jobs WHERE id = ?", (job_id,)).fetchone()
            if row:
                return self._info(row, True, 1.0)
            best, best_sim = None, 0.0
            for r in con.execute("SELECT * FROM seen_jobs"):
                s = similarity(sig, json.loads(r["signature"]))
                if s > best_sim:
                    best, best_sim = r, s
            if best is not None and best_sim >= SIMILARITY_THRESHOLD:
                return self._info(best, False, best_sim)
        return None

    def record(self, job_text: str, score: float, band: str) -> tuple[str | None, dict | None]:
        """Registra el análisis. Devuelve (id de la oferta, info de la vista anteriormente o None)."""
        if not self.enabled:
            return None, None
        previous = self.lookup(job_text)
        job_id, now = fingerprint(job_text), _now()
        with self._lock, closing(self._connect()) as con, con:
            if previous and previous["exact"]:
                con.execute("UPDATE seen_jobs SET times = times + 1, last_seen = ?, last_score = ?, "
                            "last_band = ? WHERE id = ?", (now, score, band, job_id))
            else:
                con.execute(
                    "INSERT OR REPLACE INTO seen_jobs VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                    (job_id, extract_title(job_text), now, now, score, band, json.dumps(minhash(job_text))))
                con.execute("DELETE FROM seen_jobs WHERE id IN (SELECT id FROM seen_jobs "
                            "ORDER BY last_seen DESC, rowid DESC LIMIT -1 OFFSET ?)", (self.max_entries,))
        return job_id, previous

    def list(self, limit: int = 200) -> list[dict]:
        if not self.enabled:
            return []
        with closing(self._connect()) as con:
            rows = con.execute("SELECT * FROM seen_jobs ORDER BY last_seen DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [self._info(r, True, 1.0) for r in rows]

    def delete(self, job_id: str) -> bool:
        if not self.enabled:
            return False
        with self._lock, closing(self._connect()) as con, con:
            return con.execute("DELETE FROM seen_jobs WHERE id = ?", (job_id,)).rowcount > 0

    def clear(self) -> int:
        if not self.enabled:
            return 0
        with self._lock, closing(self._connect()) as con, con:
            return con.execute("DELETE FROM seen_jobs").rowcount
