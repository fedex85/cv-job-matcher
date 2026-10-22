"""Extracción de habilidades con un diccionario (skills_db.json) y expresiones
regulares. Es determinista, rápida y explicable: cada habilidad detectada
corresponde a una entrada del diccionario."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from src.utils.helpers import fold

_LEFT = r"(?<![a-z0-9+#_])"
_RIGHT = r"(?![a-z0-9+#_])"

# Marcadores (ya sin acentos) para clasificar el contenido de una oferta.
_NICE = re.compile(
    r"\b(valorable|valorables|se valorara|se valoran|deseable|deseables|nice[- ]to[- ]have|"
    r"preferred|bonus|a plus|un plus|es plus|sera un plus|opcional|optional|no excluyente|"
    r"ideal|would be a plus|is a plus|appreciated|se valorarian)\b"
)
_IGNORE_HEAD = re.compile(
    r"\b(ofrecemos|te ofrecemos|beneficios|we offer|what we offer|benefits|perks|sobre nosotros|"
    r"about us|sobre la empresa|about the company|quienes somos|who we are|"
    r"nuestra empresa|our company|proceso de seleccion|hiring process)\b"
)
_OR = re.compile(r"(?<![a-z])(o|or)(?![a-z])|y/o|and/or")
_REQ_HEAD = re.compile(
    r"\b(requisitos|requirements|imprescindible|imprescindibles|must have|se requiere|necesario|"
    r"necesarios|que buscamos|tu perfil|el perfil|perfil|qualifications|looking for|requerimientos|"
    r"excluyente|what you bring|you have|funciones|responsabilidades|responsibilities|que haras|"
    r"tu dia a dia|what you will do|the role|el puesto|tareas|skills|habilidades|conocimientos|"
    r"experiencia)\b"
)


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    family: str | None = None
    aliases: tuple[str, ...] = ()
    case_sensitive: bool = False


@dataclass
class JobSkills:
    required: dict[str, int] = field(default_factory=dict)
    nice: dict[str, int] = field(default_factory=dict)
    # Grupos "A o B" (misma familia en la misma línea): basta con tener uno.
    alternatives: list[list[str]] = field(default_factory=list)


class SkillExtractor:
    def __init__(self, db_path: Path | str) -> None:
        raw = json.loads(Path(db_path).read_text(encoding="utf-8"))
        self.skills: dict[str, Skill] = {}
        self._patterns: list[tuple[Skill, re.Pattern[str] | None, re.Pattern[str] | None]] = []
        for item in raw["skills"]:
            skill = Skill(
                name=item["name"],
                category=item.get("category", "other"),
                family=item.get("family"),
                aliases=tuple(item.get("aliases", [])),
                case_sensitive=bool(item.get("case_sensitive", False)),
            )
            self.skills[skill.name] = skill
            insensitive = list(skill.aliases)
            sensitive: list[str] = []
            (sensitive if skill.case_sensitive else insensitive).append(skill.name)
            ci = self._compile([fold(a) for a in insensitive], 0, _LEFT, _RIGHT)
            cs = self._compile(sensitive, 0, _LEFT.replace("a-z0-9", "A-Za-z0-9"),
                               _RIGHT.replace("a-z0-9", "A-Za-z0-9"))
            self._patterns.append((skill, ci, cs))

    @staticmethod
    def _compile(terms: list[str], flags: int, left: str, right: str) -> re.Pattern[str] | None:
        if not terms:
            return None
        # alias más largos primero para que "node.js" gane a "node"
        body = "|".join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True))
        return re.compile(f"{left}(?:{body}){right}", flags)

    def extract(self, text: str) -> dict[str, int]:
        """{nombre canónico: nº de menciones} para todo el texto."""
        counts: dict[str, int] = {}
        for line in text.split("\n"):
            self._count_line(line, counts)
        return self._drop_prefixes(counts)

    @staticmethod
    def _drop_prefixes(counts: dict[str, int]) -> dict[str, int]:
        """Si se detecta "GitLab CI", no cuenta además "GitLab" por la misma mención."""
        folded = {n: fold(n) for n in counts}
        drop = {
            a for a in counts for b in counts
            if a != b and folded[b].startswith(folded[a] + " ") and counts[a] <= counts[b]
        }
        return {n: c for n, c in counts.items() if n not in drop}

    def _count_line(self, line: str, counts: dict[str, int]) -> None:
        folded = fold(line)
        for skill, ci, cs in self._patterns:
            n = (len(ci.findall(folded)) if ci else 0) + (len(cs.findall(line)) if cs else 0)
            if n:
                counts[skill.name] = counts.get(skill.name, 0) + n

    def extract_job_skills(self, text: str) -> JobSkills:
        """Separa imprescindibles y valorables según los encabezados y marcas de la oferta."""
        result = JobSkills()
        state = "required"
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            folded = fold(stripped)
            is_heading = (
                len(stripped) <= 80
                and not stripped.startswith(("-", "*", "•"))
                and (stripped.endswith(":") or not re.search(r"[.;,]$", stripped))
                and len(folded.split()) <= 8
            )
            if is_heading:
                if _IGNORE_HEAD.search(folded):
                    state = "ignore"
                elif _NICE.search(folded):
                    state = "nice"
                elif _REQ_HEAD.search(folded):
                    state = "required"
            if state == "ignore":
                continue
            line_counts: dict[str, int] = {}
            self._count_line(stripped, line_counts)
            if not line_counts:
                continue
            self._collect_alternatives(folded, line_counts, result)
            target = result.nice if (state == "nice" or _NICE.search(folded)) else result.required
            for name, n in self._drop_prefixes(line_counts).items():
                target[name] = target.get(name, 0) + n
        for name in list(result.nice):  # lo imprescindible prevalece sobre lo valorable
            if name in result.required:
                del result.nice[name]
        return result

    def _collect_alternatives(self, folded_line: str, hits: dict[str, int], result: JobSkills) -> None:
        if not _OR.search(folded_line):
            return
        by_family: dict[str, list[str]] = {}
        for name in hits:
            fam = self.skills[name].family
            if fam:
                by_family.setdefault(fam, []).append(name)
        result.alternatives.extend(sorted(g) for g in by_family.values() if len(g) > 1)

    def search(self, query: str, limit: int = 25) -> list[Skill]:
        q = fold(query.strip())
        found = [s for s in self.skills.values() if q in fold(s.name) or any(q in fold(a) for a in s.aliases)]
        return sorted(found, key=lambda s: s.name.lower())[:limit]


@lru_cache(maxsize=2)
def get_skill_extractor(db_path: str) -> SkillExtractor:
    return SkillExtractor(db_path)
