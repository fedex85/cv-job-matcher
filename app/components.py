"""Presentación de la UI: convierte el resultado del análisis en un panel (dashboard) HTML.

Sin dependencia de Gradio (se puede probar aparte). Todo texto dinámico se escapa.
Estilo oscuro por defecto con variante clara; adaptado a pantallas pequeñas.
Solo se muestran datos que la app calcula de verdad.
"""

from __future__ import annotations

import math
from datetime import datetime
from html import escape

from src.matching.messages import t
from src.nlp.entity_extractor import CEFR_LABELS, LANG_NAMES_EN, LANG_NAMES_ES

EXAMPLE_JOB = """DevOps Engineer - Remoto

Requisitos:
- 3 años de experiencia en entornos cloud (AWS o Azure)
- Docker, Kubernetes y Terraform
- CI/CD con GitHub Actions, GitLab CI o Jenkins
- Scripting en Python o Bash
- Inglés nivel B2
- Grado en Ingeniería Informática o similar

Se valorará:
- Certificación CKA, Helm, ArgoCD, Prometheus y Grafana

Qué ofrecemos:
- Trabajo 100 % remoto y horario flexible
"""

# Fuerza el tema oscuro de Gradio (el diseño está pensado para él). Si el parámetro no existe, se ignora.
FORCE_DARK_JS = "() => { document.body.classList.add('dark'); }"

CSS = """
.cvm,.cvm-panel{--bg:#f1f5f9;--card:#ffffff;--card2:#f8fafc;--border:#e2e8f0;--text:#0f172a;--muted:#64748b;
--track:#e2e8f0;--accent:#4f46e5;--accent2:#0d9488;--accent-soft:#eef2ff;--ok:#15803d;--ok-soft:#dcfce7;
--warn:#b45309;--warn-soft:#fef3c7;--bad:#b91c1c;--bad-soft:#fee2e2;--info:#0369a1;--info-soft:#e0f2fe;
--shadow:0 1px 3px rgba(15,23,42,.08);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5}
.dark .cvm,.dark .cvm-panel,[data-theme="dark"] .cvm,[data-theme="dark"] .cvm-panel{--bg:#0a1020;--card:#0f1830;
--card2:#111d3b;--border:#1f2d52;--text:#e6ecff;--muted:#8fa0c8;--track:#1b2748;--accent:#818cf8;--accent2:#22d3ee;
--accent-soft:#1c2347;--ok:#34d399;--ok-soft:#0d2f27;--warn:#fbbf24;--warn-soft:#33290d;--bad:#f87171;
--bad-soft:#3a1519;--info:#38bdf8;--info-soft:#0c2a3d;--shadow:0 6px 24px rgba(0,0,0,.35)}
body.dark,.dark .gradio-container{background:#0a1020 !important}
.cvm *{box-sizing:border-box}
.cvm-top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:4px}
.cvm-brand{display:flex;align-items:center;gap:12px}
.cvm-logo{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:1.3rem;color:#fff;
background:linear-gradient(135deg,var(--accent),var(--accent2))}
.cvm-brand h1{margin:0;font-size:1.45rem;font-weight:800;letter-spacing:-.02em;color:var(--text)}
.cvm-brand p{margin:0;color:var(--muted);font-size:.9rem}
.cvm-pills{display:flex;flex-wrap:wrap;gap:8px}
.cvm-pill{background:var(--card);border:1px solid var(--border);border-radius:999px;padding:4px 13px;font-size:.8rem;color:var(--muted)}
.cvm-step{display:flex;align-items:center;gap:10px;font-weight:700;margin:6px 0 2px;color:var(--text)}
.cvm-step i{font-style:normal;display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;
background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;font-size:.85rem}
.cvm-hint{color:var(--muted);font-size:.85rem;margin:0 0 6px 36px}
.cvm-panel{background:var(--card) !important;border:1px solid var(--border);border-radius:16px;padding:14px !important;
box-shadow:var(--shadow)}
.cvm-dash{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.cvm-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:16px 18px;box-shadow:var(--shadow);
min-width:0}
.cvm-card.span2{grid-column:span 2}
.cvm-card h3{margin:0 0 12px;font-size:1rem;font-weight:700;color:var(--text);display:flex;align-items:center;gap:10px}
.cvm-ico{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--accent-soft);
font-size:.95rem;flex:none}
.cvm-banner{border-radius:12px;padding:10px 14px;margin-bottom:14px;font-size:.92rem;border:1px solid}
.cvm-banner.warn{background:var(--warn-soft);color:var(--warn);border-color:var(--warn)}
.cvm-banner.new{background:var(--info-soft);color:var(--info);border-color:var(--info)}
.cvm-banner.err{background:var(--bad-soft);color:var(--bad);border-color:var(--bad)}
.cvm-scorebox{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.cvm-gauge{width:136px;height:136px;border-radius:50%;flex:none;display:grid;place-items:center;
background:conic-gradient(var(--g1),var(--g2) calc(var(--p)*1%),var(--track) 0)}
.cvm-gauge-in{width:106px;height:106px;border-radius:50%;background:var(--card);display:flex;flex-direction:column;
align-items:center;justify-content:center;text-align:center}
.cvm-gauge-in b{font-size:2.3rem;line-height:1}.cvm-gauge-in span{font-size:.72rem;color:var(--muted)}
.cvm-quick{flex:1;min-width:170px}.cvm-quick h4{margin:0 0 6px;font-size:.95rem}
.cvm-q{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:3px 0;font-size:.88rem}
.cvm-q span:first-child{color:var(--muted)}.cvm-q b{font-variant-numeric:tabular-nums}
.cvm-qna{opacity:.5}
.cvm-badge{display:inline-flex;align-items:center;gap:8px;margin-top:12px;padding:6px 14px;border-radius:10px;
font-weight:700;font-size:.9rem;border:1px solid var(--c);background:var(--s);color:var(--c)}
.cvm-sub{color:var(--muted);font-size:.86rem;margin:8px 0 0}
.cvm details{margin-top:10px;color:var(--muted);font-size:.85rem}.cvm summary{cursor:pointer}
.cvm details li{margin:4px 0}
.cvm-radar{display:block;width:100%;height:auto;max-height:290px}
.cvm-str{display:flex;gap:10px;align-items:flex-start;margin:8px 0;font-size:.9rem}
.cvm-check{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:.75rem;
background:var(--ok-soft);color:var(--ok);border:1px solid var(--ok)}
.cvm-opp{margin-top:12px;border:1px solid var(--border);background:var(--card2);border-radius:12px;padding:12px 14px}
.cvm-opp b{display:block;margin-bottom:2px}.cvm-opp span{color:var(--muted);font-size:.88rem}
.cvm-bars .r{display:grid;grid-template-columns:minmax(90px,38%) 1fr 42px;gap:10px;align-items:center;margin:9px 0;font-size:.88rem}
.cvm-track{height:9px;border-radius:6px;background:var(--track);overflow:hidden}
.cvm-track>div{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--g1),var(--g2))}
.cvm-bars .r span:last-child{text-align:right;font-variant-numeric:tabular-nums;color:var(--muted)}
.cvm-chip{display:inline-block;margin:3px 5px 3px 0;padding:3px 12px;border-radius:999px;font-size:.82rem;
background:var(--s);color:var(--c);border:1px solid var(--c)}
.cvm-kwhead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px}
.cvm-kwhead h3{margin:0}
.cvm-match{font-size:.82rem;padding:3px 12px;border-radius:999px;border:1px solid var(--c);background:var(--s);color:var(--c);
white-space:nowrap}
.cvm-legend{color:var(--muted);font-size:.78rem;margin:10px 0 0}
.cvm-tl{position:relative;margin:2px 0 0 8px;padding-left:20px;border-left:2px solid var(--border)}
.cvm-tl .e{position:relative;margin-bottom:14px}
.cvm-tl .e::before{content:"";position:absolute;left:-27px;top:5px;width:12px;height:12px;border-radius:50%;
background:var(--accent);box-shadow:0 0 0 4px var(--accent-soft)}
.cvm-tl .p{font-weight:700;font-size:.92rem}.cvm-tl .t{color:var(--muted);font-size:.84rem}
.cvm-tl .k{margin-top:4px}.cvm-tl .cvm-chip{font-size:.72rem;padding:1px 9px}
.cvm-rec{display:flex;gap:12px;align-items:flex-start;padding:10px 12px;margin:8px 0;border:1px solid var(--border);
background:var(--card2);border-radius:12px;font-size:.9rem}
.cvm-num{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:800;color:#fff;
background:var(--n,#6366f1)}
.cvm-tag{display:inline-block;font-size:.7rem;padding:1px 9px;border-radius:999px;background:var(--accent-soft);
color:var(--accent);font-weight:600}
.cvm-kv{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px dashed var(--border);font-size:.88rem}
.cvm-kv:last-child{border-bottom:0}.cvm-kv span:first-child{color:var(--muted)}
.cvm-two{display:grid;grid-template-columns:1fr;gap:12px}.cvm-two h4{margin:0 0 4px;font-size:.9rem}
.cvm-empty{color:var(--muted);font-size:.88rem}
.cvm-foot{color:var(--muted);font-size:.82rem;text-align:center;margin-top:8px}
.ok{--c:var(--ok);--s:var(--ok-soft);--g1:#10b981;--g2:#22d3ee}
.warn{--c:var(--warn);--s:var(--warn-soft);--g1:#f59e0b;--g2:#fbbf24}
.bad{--c:var(--bad);--s:var(--bad-soft);--g1:#ef4444;--g2:#f97316}
.mute{--c:var(--muted);--s:var(--track);--g1:#64748b;--g2:#94a3b8}
.acc{--c:var(--accent);--s:var(--accent-soft);--g1:#22d3ee;--g2:#6366f1}
@media (max-width:1100px){.cvm-dash{grid-template-columns:repeat(2,minmax(0,1fr))}.cvm-card.span2{grid-column:span 2}}
@media (max-width:720px){.cvm-dash{grid-template-columns:1fr}.cvm-card.span2{grid-column:auto}
.cvm-scorebox{justify-content:center}.cvm-brand h1{font-size:1.2rem}}
"""

_BAND_TONE = {"very_high": "ok", "high": "ok", "medium": "warn", "low": "bad", "very_low": "bad"}
_BAND_MSG = {"very_high": ("🎉", "¡Excelente encaje!"), "high": ("✅", "¡Buen encaje!"),
             "medium": ("🟡", "Vas por buen camino"), "low": ("🟠", "Hay que reforzar varias cosas"),
             "very_low": ("🔴", "Encaje bajo con esta oferta")}
_COMP_ICON = {"skills": "🧩", "semantic": "🧠", "experience": "💼", "education": "🎓", "languages": "🌐"}
_COMP_SHORT = {"skills": "Habilidades", "semantic": "Afinidad", "experience": "Experiencia",
               "education": "Formación", "languages": "Idiomas"}
_CATEGORY_ES = {
    "language": "Lenguajes", "cloud": "Cloud", "containers": "Contenedores", "iac": "Infra como código",
    "cicd": "CI/CD", "observability": "Observabilidad", "systems": "Sistemas", "networking": "Redes",
    "security": "Seguridad", "database": "Bases de datos", "data": "Datos", "framework": "Frameworks",
    "frontend": "Frontend", "practice": "Prácticas", "methodology": "Metodologías", "tools": "Herramientas",
    "ai": "IA / ML", "virtualization": "Virtualización", "other": "Otras",
}
_REC_COLORS = ["#6366f1", "#a855f7", "#0ea5e9", "#ec4899", "#f59e0b"]


def hero_html() -> str:
    return (
        f"<style>{CSS}</style><div class='cvm'><div class='cvm-top'><div class='cvm-brand'>"
        "<div class='cvm-logo'>✦</div><div><h1>CV Matcher</h1><p>Tu CV frente a cada oferta, explicado</p></div></div>"
        "<div class='cvm-pills'><span class='cvm-pill'>🔒 Tu CV no se guarda</span>"
        "<span class='cvm-pill'>🌐 Español e inglés</span><span class='cvm-pill'>🧠 Sin cajas negras</span></div>"
        "</div></div>"
    )


def step_html(n: int, title: str, hint: str = "") -> str:
    h = f"<p class='cvm-hint'>{escape(hint)}</p>" if hint else ""
    return f"<div class='cvm'><div class='cvm-step'><i>{n}</i>{escape(title)}</div>{h}</div>"


def empty_state() -> str:
    return (
        "<div class='cvm'><div class='cvm-card' style='text-align:center;padding:42px 18px'>"
        "<div style='font-size:2.6rem'>📄➜🎯</div><h3 style='justify-content:center;margin-top:10px'>Aquí verás tu panel de resultados</h3>"
        "<p class='cvm-empty'>Sube tu CV, pega la oferta y pulsa <b>Analizar mi CV</b>.<br>"
        "Puedes probar con la oferta de ejemplo.</p></div></div>"
    )


def error_html(message: str) -> str:
    return f"<div class='cvm'><div class='cvm-banner err'>⚠️ {escape(message)}</div></div>"


def format_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def seen_banner(result: dict) -> str:
    seen = result.get("seen_before")
    if not seen:
        if result.get("job_id"):
            return "<div class='cvm-banner new'>🆕 Oferta nueva: la he añadido a tu historial de ofertas vistas.</div>"
        return ""
    when = escape(format_date(seen["last_seen"]))
    title = escape(seen["title"])
    if seen["exact"]:
        times = seen["times"]
        veces = "1 vez" if times == 1 else f"{times} veces"
        return (f"<div class='cvm-banner warn'>🔁 <b>Ya viste esta oferta</b> ({veces}; la última, el {when}, "
                f"con nota {seen['last_score']:.0f}/100): «{title}».</div>")
    return (f"<div class='cvm-banner warn'>🔁 <b>Muy parecida a otra que ya viste</b> ({round(seen['similarity'] * 100)} % de "
            f"parecido, el {when}): «{title}». Puede ser la misma oferta republicada.</div>")


# ------------------------------------------------------------------ tarjetas
def _skill_counts(r: dict) -> tuple[int, int]:
    s = r["skills"]
    total = len(s["matched"]) + len(s["partial"]) + len(s["missing_required"]) + len(s["missing_nice"])
    return len(s["matched"]), total


def _card_score(r: dict) -> str:
    tone = _BAND_TONE.get(r["band"], "mute")
    icon, msg = _BAND_MSG.get(r["band"], ("", r["band_label"]))
    rows = []
    for c in r["components"]:
        label = _COMP_SHORT.get(c["key"], c["label"])
        if c["applicable"]:
            rows.append(f"<div class='cvm-q'><span>{_COMP_ICON.get(c['key'], '')} {label}</span><b>{c['score']:.0f}/100</b></div>")
        else:
            rows.append(f"<div class='cvm-q cvm-qna'><span>{_COMP_ICON.get(c['key'], '')} {label}</span><b>—</b></div>")
    got, total = _skill_counts(r)
    sub = f"Cubres {got} de {total} habilidades que menciona la oferta." if total else r["band_label"]
    notes = "".join(f"<li><b>{escape(c['label'])}:</b> {escape(c['note'])}</li>" for c in r["components"])
    meta = r["meta"]
    ms = meta["elapsed_ms"]
    took = "menos de 1 s" if ms < 1000 else f"{ms / 1000:.1f} s"
    return (
        f"<div class='cvm-card {tone}'><div class='cvm-scorebox'>"
        f"<div class='cvm-gauge' style='--p:{r['score']:.0f}'><div class='cvm-gauge-in'><b style='color:var(--c)'>"
        f"{r['score']:.0f}</b><span>/100 · nota global</span></div></div>"
        f"<div class='cvm-quick'><h4>Resumen rápido</h4>{''.join(rows)}</div></div>"
        f"<div class='cvm-badge'>{icon} {escape(msg)}</div><p class='cvm-sub'>{escape(sub)}</p>"
        f"<details><summary>¿Cómo se calculó cada bloque? · {took}</summary><ul>{notes}</ul></details></div>"
    )


def _radar_svg(r: dict) -> str:
    comps = r["components"]
    n, cx, cy, rad = len(comps), 150, 128, 88
    pts = lambda frac, i: (cx + rad * frac * math.cos(math.radians(-90 + i * 360 / n)),  # noqa: E731
                           cy + rad * frac * math.sin(math.radians(-90 + i * 360 / n)))
    out = ["<svg class='cvm-radar' viewBox='0 0 300 262' role='img' aria-label='Gráfico de radar de la compatibilidad'>"]
    for ring in (0.25, 0.5, 0.75, 1.0):
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pts(ring, i) for i in range(n)))
        out.append(f"<polygon points='{poly}' fill='none' style='stroke:var(--muted)' stroke-opacity='.35' stroke-width='1'/>")
    for i in range(n):
        x, y = pts(1.0, i)
        out.append(f"<line x1='{cx}' y1='{cy}' x2='{x:.1f}' y2='{y:.1f}' style='stroke:var(--muted)' stroke-opacity='.35' stroke-width='1'/>")
    vals = [c["score"] / 100 if c["applicable"] else 0.0 for c in comps]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pts(v, i) for i, v in enumerate(vals)))
    out.append(f"<polygon points='{poly}' style='fill:var(--accent);stroke:var(--accent)' fill-opacity='.28' stroke-width='2'/>")
    for i, v in enumerate(vals):
        x, y = pts(v, i)
        out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.5' style='fill:var(--accent)'/>")
    for i, c in enumerate(comps):
        x, y = pts(1.0, i)
        lx, ly = pts(1.0 + 24 / rad, i)
        cos = math.cos(math.radians(-90 + i * 360 / n))
        anchor = "start" if cos > 0.3 else ("end" if cos < -0.3 else "middle")
        value = f"{c['score']:.0f}" if c["applicable"] else "n/a"
        out.append(
            f"<text x='{lx:.1f}' y='{ly:.1f}' text-anchor='{anchor}' style='fill:var(--text)' font-size='11'>"
            f"<tspan x='{lx:.1f}'>{escape(_COMP_SHORT.get(c['key'], c['label']))}</tspan>"
            f"<tspan x='{lx:.1f}' dy='13' style='fill:var(--muted)'>{value}</tspan></text>")
    out.append("</svg>")
    return "".join(out)


def _card_radar(r: dict) -> str:
    return (f"<div class='cvm-card'><h3><span class='cvm-ico'>🕸️</span>Perfil de compatibilidad</h3>"
            f"{_radar_svg(r)}</div>")


def _strengths(r: dict) -> list[str]:
    comps = {c["key"]: c for c in r["components"] if c["applicable"]}
    out: list[str] = []
    s = r["skills"]
    if s["matched"]:
        top = ", ".join(s["matched"][:4])
        out.append(f"Dominas tecnologías clave de la oferta: {top}.")
    cv, job = r["cv_profile"], r["job_profile"]
    if "experience" in comps and comps["experience"]["score"] >= 80:
        need = f" (la oferta pide {job['required_years']:.0f})" if job["required_years"] else ""
        out.append(f"Experiencia suficiente: ~{cv['years_experience']:.0f} años{need}.")
    if "education" in comps and comps["education"]["score"] >= 100:
        out.append("Tu formación cumple lo que pide la oferta.")
    if "languages" in comps and comps["languages"]["score"] >= 100:
        out.append("Tus idiomas cubren el nivel requerido.")
    if "skills" in comps and comps["skills"]["detail"].get("required_coverage", 0) >= 0.8:
        out.append("Cubres la gran mayoría de los requisitos imprescindibles.")
    return out[:4]


def _card_strengths(r: dict) -> str:
    items = _strengths(r)
    body = "".join(f"<div class='cvm-str'><span class='cvm-check'>✓</span><span>{escape(x)}</span></div>" for x in items) \
        or "<p class='cvm-empty'>Todavía no destacan fortalezas claras frente a esta oferta.</p>"
    opp_src = r["tips"][0] if r["tips"] else (r["advice"]["recommendations"][0] if r["advice"]["recommendations"] else "")
    opp = (f"<div class='cvm-opp'><b>💡 Oportunidad de mejora</b><span>{escape(opp_src)}</span></div>" if opp_src else "")
    return f"<div class='cvm-card'><h3><span class='cvm-ico'>💪</span>Fortalezas destacadas</h3>{body}{opp}</div>"


def _card_categories(r: dict) -> str:
    cats = r["skills"].get("by_category", [])
    if not cats:
        body = "<p class='cvm-empty'>La oferta no menciona habilidades reconocibles.</p>"
    else:
        rows = []
        for c in cats[:7]:
            label = _CATEGORY_ES.get(c["category"], c["category"].title())
            rows.append(f"<div class='r'><span>{escape(label)}</span><div class='cvm-track'>"
                        f"<div style='width:{c['covered_pct']}%'></div></div><span>{c['covered_pct']}%</span></div>")
        body = f"<div class='cvm-bars acc'>{''.join(rows)}</div>"
    return (f"<div class='cvm-card'><h3><span class='cvm-ico'>📊</span>Cobertura por área</h3>{body}"
            "<p class='cvm-legend'>Qué parte de lo que pide la oferta en cada área aparece en tu CV.</p></div>")


def _chips(items: list[str], tone: str) -> str:
    return "".join(f"<span class='cvm-chip {tone}'>{escape(i)}</span>" for i in items)


def _card_keywords(r: dict) -> str:
    s = r["skills"]
    skills_comp = next((c for c in r["components"] if c["key"] == "skills" and c["applicable"]), None)
    match = ""
    if skills_comp:
        pct = round(skills_comp["detail"].get("required_coverage", 0) * 100)
        tone = "ok" if pct >= 70 else ("warn" if pct >= 40 else "bad")
        match = f"<span class='cvm-match {tone}'>Imprescindibles: {pct}%</span>"
    partial = [f"{p['required']} ≈ {p['via']}" for p in s["partial"]]
    body = (_chips(s["matched"], "ok") + _chips(partial, "warn") + _chips(s["missing_required"], "bad")
            + _chips(s["missing_nice"], "mute"))
    if not body:
        body = "<p class='cvm-empty'>La oferta no menciona habilidades reconocibles.</p>"
    return (f"<div class='cvm-card'><div class='cvm-kwhead'><h3><span class='cvm-ico'>🏷️</span>Palabras clave</h3>{match}</div>"
            f"<div>{body}</div><p class='cvm-legend'>🟢 las tienes · 🟡 parecida · 🔴 falta (imprescindible) · ⚪ falta (valorable)</p></div>")


def _card_timeline(r: dict) -> str:
    tl = r["cv_profile"].get("timeline", [])
    if not tl:
        body = ("<p class='cvm-empty'>No detecté periodos con fechas en tu CV. Usa un formato como "
                "«2018 – 2021» o «ene 2020 – actualidad» para verlos aquí.</p>")
    else:
        entries = []
        for e in tl:
            sk = f"<div class='k'>{_chips(e['skills'], 'acc')}</div>" if e["skills"] else ""
            entries.append(f"<div class='e'><div class='p'>{escape(e['period'])} · {e['years']:.0f} "
                           f"{'año' if round(e['years']) == 1 else 'años'}</div><div class='t'>{escape(e['title'])}</div>{sk}</div>")
        body = f"<div class='cvm-tl'>{''.join(entries)}</div>"
    return f"<div class='cvm-card'><h3><span class='cvm-ico'>🕒</span>Tu trayectoria detectada</h3>{body}</div>"


def _card_recs(r: dict) -> str:
    adv = r["advice"]
    tag = "IA · Groq" if adv["source"] == "llm" else "Reglas"
    recs = "".join(
        f"<div class='cvm-rec'><span class='cvm-num' style='--n:{_REC_COLORS[i % len(_REC_COLORS)]}'>{i + 1}</span>"
        f"<span>{escape(x)}</span></div>" for i, x in enumerate(adv["recommendations"]))
    extra = ""
    if adv["source"] == "llm" and r["tips"]:
        extra = ("<details><summary>Ver también los consejos automáticos</summary><ul>"
                 + "".join(f"<li>{escape(x)}</li>" for x in r["tips"]) + "</ul></details>")
    warn = ""
    if adv.get("llm_error"):
        warn = (f"<p class='cvm-sub'>La IA no respondió ({escape(adv['llm_error'])}); estos consejos son por reglas.</p>")
    for w in r.get("warnings", []):
        warn += f"<div class='cvm-banner warn' style='margin:8px 0 0'>⚠️ {escape(w)}</div>"
    return (f"<div class='cvm-card span2'><h3><span class='cvm-ico'>✨</span>Recomendaciones personalizadas "
            f"<span class='cvm-tag'>{tag}</span></h3><p style='margin:0 0 6px'><b>{escape(adv['summary'])}</b></p>"
            f"{recs}{extra}{warn}</div>")


def _card_understood(r: dict) -> str:
    lang = r["language"]
    names = LANG_NAMES_EN if lang == "en" else LANG_NAMES_ES

    def langs(d: dict) -> str:
        return ", ".join(f"{names.get(k, k)} {CEFR_LABELS.get(v, '?')}" for k, v in d.items()) or "—"

    cv, job = r["cv_profile"], r["job_profile"]
    years_job = f"{job['required_years']:.0f} años" if job["required_years"] else "no indica"
    edu_job = t(lang, f"edu.level.{job['education_level']}") if job["education_level"] else "no indica"
    left = [("Experiencia", f"{cv['years_experience']:.1f} años"),
            ("Formación", t(lang, f"edu.level.{cv['education_level']}")), ("Idiomas", langs(cv["languages"]))]
    right = [("Experiencia", years_job), ("Formación", edu_job), ("Idiomas", langs(job["languages"]))]

    def col(title: str, kv: list[tuple[str, str]]) -> str:
        rows = "".join(f"<div class='cvm-kv'><span>{a}</span><span>{escape(b)}</span></div>" for a, b in kv)
        return f"<div><h4>{title}</h4>{rows}</div>"

    note = ("<p class='cvm-sub'>El idioma de tu CV se ha dado por conocido (nivel C1).</p>"
            if cv.get("languages_inferred") else "")
    return (f"<div class='cvm-card'><h3><span class='cvm-ico'>🔎</span>Qué he entendido</h3>"
            f"<div class='cvm-two'>{col('Tu CV', left)}{col('La oferta', right)}</div>{note}</div>")


def render_results(r: dict) -> str:
    return ("<div class='cvm'>" + seen_banner(r) + "<div class='cvm-dash'>"
            + _card_score(r) + _card_radar(r) + _card_strengths(r)
            + _card_categories(r) + _card_keywords(r) + _card_timeline(r)
            + _card_recs(r) + _card_understood(r) + "</div></div>")


HISTORY_HEADERS = ["Última vez", "Oferta", "Nota", "Veces"]


def history_rows(items: list[dict]) -> list[list]:
    return [[format_date(i["last_seen"]), i["title"], round(i["last_score"]), i["times"]] for i in items]
