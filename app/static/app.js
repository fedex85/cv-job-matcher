/* CV Matcher · interfaz. Sin dependencias externas. Todo texto dinámico se inserta con textContent (sin HTML en bruto). */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SVG_NS = "http://www.w3.org/2000/svg";

  const EXAMPLE_JOB = `DevOps Engineer - Remoto

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
`;
  const BAND_TONE = { very_high: "ok", high: "ok", medium: "warn", low: "bad", very_low: "bad" };
  const BAND_MSG = { very_high: "🎉 ¡Excelente encaje!", high: "✅ ¡Buen encaje!", medium: "🟡 Vas por buen camino",
    low: "🟠 Hay que reforzar varias cosas", very_low: "🔴 Encaje bajo con esta oferta" };
  const COMP = { skills: ["🧩", "Habilidades"], semantic: ["🧠", "Afinidad"], experience: ["💼", "Experiencia"],
    education: ["🎓", "Formación"], languages: ["🌐", "Idiomas"] };
  const CATEGORY = { language: "Lenguajes", cloud: "Cloud", containers: "Contenedores", iac: "Infra como código",
    cicd: "CI/CD", observability: "Observabilidad", systems: "Sistemas", networking: "Redes", security: "Seguridad",
    database: "Bases de datos", data: "Datos", framework: "Frameworks", frontend: "Frontend", practice: "Prácticas",
    methodology: "Metodologías", tools: "Herramientas", ai: "IA / ML", virtualization: "Virtualización", other: "Otras" };
  const EDU = ["no detectada", "FP / ciclo formativo", "grado / universitario", "máster", "doctorado"];
  const CEFR = ["?", "A1", "A2", "B1", "B2", "C1", "C2"];
  const REC_COLORS = ["#6366f1", "#a855f7", "#0ea5e9", "#ec4899", "#f59e0b"];
  const TITLES = { analyze: "Analizar una oferta", history: "Ofertas vistas", how: "Cómo se calcula la nota" };

  const state = { health: null, busy: false, last: null };

  // ---------------------------------------------------------------- utilidades DOM
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    append(el, kids);
    return el;
  }
  function s(tag, attrs, ...kids) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
    append(el, kids);
    return el;
  }
  function append(el, kids) {
    for (const k of kids.flat()) if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  }
  const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
  const num = (n, d = 0) => Number(n).toFixed(d);
  const fmtDate = (iso) => { const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }); };
  const langName = (code) => { try { return new Intl.DisplayNames(["es"], { type: "language" }).of(code) || code; } catch { return code; } };

  // ---------------------------------------------------------------- red
  function headers() {
    const k = $("api-key").value.trim();
    return k ? { "X-API-Key": k } : {};
  }
  async function api(path, opts = {}) {
    const r = await fetch(path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
    let data = null;
    try { data = await r.json(); } catch { /* cuerpo vacío */ }
    if (!r.ok) {
      const msg = data && data.error ? data.error.message : `Error ${r.status}`;
      const e = new Error(r.status === 401 ? "Falta la clave de acceso o no es correcta." : msg);
      e.status = r.status;
      throw e;
    }
    return data;
  }

  // ---------------------------------------------------------------- tema y navegación
  function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    $("theme").textContent = t === "dark" ? "Tema claro" : "Tema oscuro";
    try { localStorage.setItem("cvm-theme", t); } catch { /* sin almacenamiento */ }
  }
  function initTheme() {
    let t = "dark";
    try { t = localStorage.getItem("cvm-theme") || "dark"; } catch { /* ignorar */ }
    setTheme(t === "light" ? "light" : "dark");
    $("theme").addEventListener("click", () => setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
  }
  function showView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("is-active", v.id === `view-${name}`));
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("is-active", b.dataset.view === name));
    $("page-title").textContent = TITLES[name];
    closeMenu();
    if (name === "history") loadHistory();
    if (name === "how") renderHow();
    window.scrollTo(0, 0);
  }
  function closeMenu() { $("side").classList.remove("is-open"); $("burger").setAttribute("aria-expanded", "false"); }

  // ---------------------------------------------------------------- estado del servidor
  async function loadHealth() {
    const st = $("status");
    try {
      const r = await fetch("/health");
      state.health = await r.json();
      st.className = "status ok";
      $("status-text").textContent = state.health.llm ? "Servidor listo · IA Groq activa" : "Servidor listo · sin IA (consejos por reglas)";
      $("key-wrap").hidden = !state.health.auth_required;
      const llm = $("use-llm");
      if (!state.health.llm) { llm.checked = false; llm.disabled = true; llm.closest(".chk").classList.add("is-off"); llm.closest(".chk").title = "Define GROQ_API_KEY en .env para activarlo"; }
    } catch {
      st.className = "status bad";
      $("status-text").textContent = "Sin conexión con el servidor";
    }
  }

  // ---------------------------------------------------------------- formulario
  function setFileLabel(file) {
    const drop = $("drop");
    drop.classList.toggle("has-file", !!file);
    $("drop-main").textContent = file ? file.name : "Arrastra tu CV aquí o haz clic para elegirlo";
    $("drop-sub").textContent = file ? `${(file.size / 1024).toFixed(0)} KB · haz clic para cambiarlo` : "PDF, DOCX o TXT · hasta 5 MB";
  }
  function showFormError(msg) {
    const el = $("form-error");
    el.hidden = !msg;
    el.textContent = msg || "";
  }
  function initForm() {
    const drop = $("drop"), cv = $("cv");
    cv.addEventListener("change", () => setFileLabel(cv.files[0]));
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("is-over"); }));
    drop.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files.length) { cv.files = e.dataTransfer.files; setFileLabel(cv.files[0]); }
    });
    $("example").addEventListener("click", () => { $("job").value = EXAMPLE_JOB; $("job").focus(); });
    $("form").addEventListener("submit", onSubmit);
  }
  async function onSubmit(e) {
    e.preventDefault();
    if (state.busy) return;
    showFormError("");
    const cv = $("cv").files[0], jobFile = $("job-file").files[0], job = $("job").value.trim();
    if (!cv) return showFormError("Sube tu CV (PDF, DOCX o TXT).");
    if (!job && !jobFile) return showFormError("Pega el texto de la oferta o sube un archivo con ella.");
    const fd = new FormData();
    fd.append("cv_file", cv);
    if (jobFile) fd.append("job_file", jobFile); else fd.append("job_text", job);
    fd.append("use_llm", $("use-llm").checked ? "true" : "false");
    fd.append("remember_job", $("remember").checked ? "true" : "false");
    state.last = { cv, jobFile: jobFile || null, job };
    const btn = $("go");
    state.busy = true; btn.disabled = true; btn.textContent = "Analizando…";
    try {
      const result = await api("/api/v1/analyze", { method: "POST", body: fd });
      renderResults(result);
      $("results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showFormError(err.message || "No se pudo analizar. Inténtalo de nuevo.");
    } finally {
      state.busy = false; btn.disabled = false; btn.textContent = "Analizar mi CV";
    }
  }

  // ---------------------------------------------------------------- tarjetas
  const card = (icon, title, body, cls = "", extra = null) =>
    h("section", { class: `card ${cls}` }, h("h3", {}, h("span", { class: "ico", "aria-hidden": "true" }, icon), title, extra), body);
  const chips = (items, tone) => items.map((t) => h("span", { class: `chip ${tone}` }, t));
  const none = (t) => h("p", { class: "none" }, t);

  function skillCounts(r) {
    const k = r.skills;
    return [k.matched.length, k.matched.length + k.partial.length + k.missing_required.length + k.missing_nice.length];
  }

  function cardScore(r) {
    const tone = BAND_TONE[r.band] || "warn";
    const C = 2 * Math.PI * 62;
    const val = s("circle", { class: "val", cx: 74, cy: 74, r: 62, fill: "none", "stroke-width": 12, "stroke-linecap": "round",
      "stroke-dasharray": C.toFixed(1), "stroke-dashoffset": C.toFixed(1) });
    const ring = h("div", { class: `ring ${tone}`, role: "img", "aria-label": `Nota global ${num(r.score)} sobre 100` },
      s("svg", { viewBox: "0 0 148 148" }, s("circle", { class: "trk", cx: 74, cy: 74, r: 62, fill: "none", "stroke-width": 12 }), val),
      h("div", { class: "ring-in" }, h("b", {}, num(r.score)), h("span", {}, "de 100")));
    requestAnimationFrame(() => requestAnimationFrame(() => val.setAttribute("stroke-dashoffset", (C * (1 - r.score / 100)).toFixed(1))));
    const rows = r.components.map((c) => h("div", { class: `q ${c.applicable ? "" : "na"}` },
      h("span", {}, `${COMP[c.key] ? COMP[c.key][0] : ""} ${COMP[c.key] ? COMP[c.key][1] : c.label}`), h("b", {}, c.applicable ? `${num(c.score)}/100` : "—")));
    const [got, total] = skillCounts(r);
    const ms = r.meta.elapsed_ms;
    const took = ms < 1000 ? "menos de 1 s" : `${(ms / 1000).toFixed(1)} s`;
    const notes = r.components.map((c) => h("li", {}, h("b", {}, `${c.label}: `), c.note));
    const body = h("div", {},
      h("div", { class: "score" }, ring, h("div", { class: "quick" }, h("h4", {}, "Resumen rápido"), rows)),
      h("span", { class: `badge ${tone}` }, BAND_MSG[r.band] || r.band_label),
      h("p", { class: "sub" }, total ? `Cubres ${got} de ${total} habilidades que menciona la oferta.` : r.band_label),
      h("details", {}, h("summary", {}, `¿Cómo se calculó cada bloque? · ${took}`), h("ul", {}, notes)));
    return card("🎯", "Compatibilidad", body);
  }

  function cardRadar(r) {
    const comps = r.components, n = comps.length, cx = 150, cy = 130, rad = 86;
    const pt = (f, i) => { const a = (-90 + (i * 360) / n) * Math.PI / 180; return [cx + rad * f * Math.cos(a), cy + rad * f * Math.sin(a)]; };
    const poly = (f) => comps.map((_, i) => pt(f, i).map((v) => v.toFixed(1)).join(",")).join(" ");
    const svg = s("svg", { class: "radar", viewBox: "0 0 300 262", role: "img", "aria-label": "Radar de compatibilidad por bloque" });
    [0.25, 0.5, 0.75, 1].forEach((f) => svg.append(s("polygon", { class: "grid", points: poly(f) })));
    comps.forEach((_, i) => { const [x, y] = pt(1, i); svg.append(s("line", { class: "grid", x1: cx, y1: cy, x2: x.toFixed(1), y2: y.toFixed(1) })); });
    const vals = comps.map((c) => (c.applicable ? c.score / 100 : 0));
    svg.append(s("polygon", { class: "shape", points: vals.map((v, i) => pt(v, i).map((q) => q.toFixed(1)).join(",")).join(" ") }));
    vals.forEach((v, i) => { const [x, y] = pt(v, i); svg.append(s("circle", { class: "pt", cx: x.toFixed(1), cy: y.toFixed(1), r: 3.5 })); });
    comps.forEach((c, i) => {
      const [lx, ly] = pt(1 + 22 / rad, i);
      const cos = Math.cos((-90 + (i * 360) / n) * Math.PI / 180);
      const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
      const t = s("text", { x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": anchor });
      const a = s("tspan", { x: lx.toFixed(1) }); a.textContent = COMP[c.key] ? COMP[c.key][1] : c.label;
      const b = s("tspan", { x: lx.toFixed(1), dy: 13, class: "rv" }); b.textContent = c.applicable ? num(c.score) : "n/a";
      t.append(a, b); svg.append(t);
    });
    return card("🕸️", "Perfil de compatibilidad", svg);
  }

  function strengths(r) {
    const comps = Object.fromEntries(r.components.filter((c) => c.applicable).map((c) => [c.key, c]));
    const out = [], k = r.skills, cv = r.cv_profile, job = r.job_profile;
    if (k.matched.length) out.push(`Dominas tecnologías clave de la oferta: ${k.matched.slice(0, 4).join(", ")}.`);
    if (comps.experience && comps.experience.score >= 80)
      out.push(`Experiencia suficiente: ~${num(cv.years_experience)} años${job.required_years ? ` (la oferta pide ${num(job.required_years)})` : ""}.`);
    if (comps.education && comps.education.score >= 100) out.push("Tu formación cumple lo que pide la oferta.");
    if (comps.languages && comps.languages.score >= 100) out.push("Tus idiomas cubren el nivel requerido.");
    if (comps.skills && (comps.skills.detail.required_coverage || 0) >= 0.8) out.push("Cubres la gran mayoría de los requisitos imprescindibles.");
    return out.slice(0, 4);
  }
  function cardStrengths(r) {
    const items = strengths(r);
    const body = h("div", {}, items.length ? items.map((t) => h("div", { class: "str" }, h("span", { class: "check", "aria-hidden": "true" }, "✓"), h("span", {}, t)))
      : none("Todavía no destacan fortalezas claras frente a esta oferta."));
    const opp = r.tips[0] || (r.advice.recommendations || [])[0];
    if (opp) body.append(h("div", { class: "opp" }, h("b", {}, "💡 Oportunidad de mejora"), opp));
    return card("💪", "Fortalezas destacadas", body);
  }

  function cardCategories(r) {
    const cats = r.skills.by_category || [];
    const body = cats.length
      ? h("div", {}, h("div", { class: "bars" }, cats.slice(0, 7).map((c) => h("div", { class: "bar" },
          h("span", {}, CATEGORY[c.category] || c.category), h("div", { class: "t" }, (() => { const i = h("i"); i.style.width = `${c.covered_pct}%`; return i; })()),
          h("span", { class: "n" }, `${c.covered_pct}%`)))),
        h("p", { class: "legend" }, "Qué parte de lo que pide la oferta, en cada área, aparece en tu CV."))
      : none("La oferta no menciona habilidades reconocibles.");
    return card("📊", "Cobertura por área", body);
  }

  function cardKeywords(r) {
    const k = r.skills;
    const sc = r.components.find((c) => c.key === "skills" && c.applicable);
    let match = null;
    if (sc) {
      const pct = Math.round((sc.detail.required_coverage || 0) * 100);
      match = h("span", { class: `match ${pct >= 70 ? "ok" : pct >= 40 ? "warn" : "bad"}` }, `Imprescindibles: ${pct}%`);
    }
    const all = [...chips(k.matched, "ok"), ...chips(k.partial.map((p) => `${p.required} ≈ ${p.via}`), "warn"),
      ...chips(k.missing_required, "bad"), ...chips(k.missing_nice, "mute")];
    const body = all.length ? h("div", {}, h("div", { class: "chips" }, all),
      h("p", { class: "legend" }, "Verde: la tienes · amarillo: parecida · rojo: falta (imprescindible) · gris: falta (se valora)"))
      : none("La oferta no menciona habilidades reconocibles.");
    return card("🏷️", "Palabras clave", body, "", match);
  }

  function cardTimeline(r) {
    const tl = r.cv_profile.timeline || [];
    const body = tl.length
      ? h("div", { class: "tl" }, tl.map((e) => h("div", { class: "e" },
          h("div", { class: "p" }, `${e.period} · ${Math.round(e.years)} ${Math.round(e.years) === 1 ? "año" : "años"}`),
          h("div", { class: "tt" }, e.title), e.skills.length ? h("div", { class: "chips" }, chips(e.skills, "acc")) : null)))
      : none("No detecté periodos con fechas en tu CV. Usa un formato como «2018 – 2021» o «ene 2020 – actualidad» para verlos aquí.");
    return card("🕒", "Tu trayectoria detectada", body);
  }

  function cardAts(r) {
    const a = r.ats;
    const ICON = { ok: "✓", warn: "!", bad: "✕" };
    const rows = a.checks.map((c) => h("li", { class: `ats-row ${c.status}` },
      h("span", { class: "ats-ico", "aria-hidden": "true" }, ICON[c.status]),
      h("div", {}, h("b", {}, c.label), h("p", {}, c.detail))));
    const head = h("div", { class: "ats-head" },
      h("div", { class: `ats-score ${a.band}` }, h("b", {}, String(a.score)), h("span", {}, "/100")),
      h("p", {}, a.score >= 80 ? "Tu CV se lee bien para un filtro automático." : a.score >= 60 ? "Pasaría el filtro, pero hay cosas fáciles de mejorar." : "Algunos filtros automáticos podrían leerlo mal. Empieza por lo marcado en rojo."));
    return card("🤖", "Filtros ATS", h("div", {}, head, h("ul", { class: "ats-list" }, rows), h("p", { class: "legend" }, a.note)), "span2");
  }

  function cardRecs(r) {
    const a = r.advice;
    const body = h("div", {}, h("p", {}, h("b", {}, a.summary)),
      h("div", { class: "recs" }, a.recommendations.map((t, i) => {
        const n = h("span", { class: "num" }, String(i + 1));
        n.style.setProperty("--n", REC_COLORS[i % REC_COLORS.length]);
        return h("div", { class: "rec" }, n, h("span", {}, t));
      })));
    if (a.source === "llm" && r.tips.length)
      body.append(h("details", {}, h("summary", {}, "Ver también los consejos automáticos"), h("ul", {}, r.tips.map((t) => h("li", {}, t)))));
    if (a.llm_error) body.append(h("p", { class: "sub" }, `La IA no respondió (${a.llm_error}); estos consejos son por reglas.`));
    (r.warnings || []).forEach((w) => body.append(h("div", { class: "warnline" }, `⚠️ ${w}`)));
    return card("✨", "Recomendaciones personalizadas", body, "span3", h("span", { class: "tag" }, a.source === "llm" ? "IA · Groq" : "Reglas"));
  }

  function cardUnderstood(r) {
    const langs = (d) => Object.entries(d).map(([k, v]) => `${langName(k)} ${CEFR[v] || "?"}`).join(", ") || "—";
    const cv = r.cv_profile, job = r.job_profile;
    const col = (title, rows) => h("div", {}, h("h4", {}, title), rows.map(([a, b]) => h("div", { class: "kv" }, h("span", {}, a), h("span", {}, b))));
    const body = h("div", {}, h("div", { class: "two" },
      col("Tu CV", [["Experiencia", `${num(cv.years_experience, 1)} años`], ["Formación", EDU[cv.education_level] || "—"], ["Idiomas", langs(cv.languages)]]),
      col("La oferta", [["Experiencia", job.required_years ? `${num(job.required_years)} años` : "no indica"],
        ["Formación", job.education_level ? EDU[job.education_level] : "no indica"], ["Idiomas", langs(job.languages)]])));
    if (cv.languages_inferred) body.append(h("p", { class: "sub" }, "El idioma de tu CV se ha dado por conocido (nivel C1)."));
    return card("🔎", "Qué he entendido", body);
  }

  function banner(r) {
    const seen = r.seen_before;
    if (!seen) return r.job_id ? h("div", { class: "banner new" }, "🆕 Oferta nueva: la he añadido a tu historial de ofertas vistas.") : null;
    const veces = seen.times === 1 ? "1 vez" : `${seen.times} veces`;
    if (seen.exact)
      return h("div", { class: "banner seen" }, h("b", {}, "🔁 Ya viste esta oferta"), ` (${veces}; la última, el ${fmtDate(seen.last_seen)}, con nota ${num(seen.last_score)}/100): «${seen.title}».`);
    return h("div", { class: "banner seen" }, h("b", {}, "🔁 Muy parecida a otra que ya viste"),
      ` (${Math.round(seen.similarity * 100)} % de parecido, el ${fmtDate(seen.last_seen)}): «${seen.title}». Puede ser la misma oferta republicada.`);
  }

  // ---------------------------------------------------------------- asistente de IA
  const AI_TASKS = [["rewrite", "✍️", "Reescribir mis logros"], ["summary", "🧾", "Resumen de perfil"],
    ["cover", "💌", "Carta de presentación"], ["interview", "🎤", "Preguntas de entrevista"]];
  const AI_TITLES = Object.fromEntries(AI_TASKS.map(([k, , l]) => [k, l]));

  async function copyText(text, btn) {
    try { await navigator.clipboard.writeText(text); btn.textContent = "¡Copiado!"; }
    catch { btn.textContent = "Selecciona y copia"; }
    setTimeout(() => { btn.textContent = "Copiar"; }, 1800);
  }
  function checkNote(check) {
    if (!check) return null;
    const parts = [];
    if (check.skills && check.skills.length) parts.push(`tecnologías que no están en tu CV: ${check.skills.join(", ")}`);
    if (check.numbers && check.numbers.length) parts.push(`cifras que no están en tu CV: ${check.numbers.join(", ")}`);
    return parts.length ? h("p", { class: "warnline" }, `⚠️ Revisa antes de usarlo — ${parts.join("; ")}. No afirmes nada que no hayas hecho.`) : null;
  }
  function aiPanel(task, bodyKids, copy) {
    const btn = h("button", { class: "ghost", type: "button" }, "Copiar");
    btn.addEventListener("click", () => copyText(copy, btn));
    return h("div", { class: "ai-panel", id: `ai-${task}` }, h("div", { class: "ai-head" }, h("h4", {}, AI_TITLES[task]), copy ? btn : null), bodyKids);
  }
  function renderAi(task, res) {
    if (res.error) return h("div", { class: "ai-panel", id: `ai-${task}` }, h("h4", {}, AI_TITLES[task]), h("p", { class: "form-error" }, res.error));
    if (task === "rewrite") {
      const body = res.items.map((it) => h("div", { class: "ai-pair" },
        h("div", {}, h("small", {}, "Tu CV dice"), h("p", { class: "ai-before" }, it.original)),
        h("div", {}, h("small", {}, "Podría decir"), h("p", { class: "ai-after" }, it.rewritten),
          it.keywords.length ? h("div", { class: "chips" }, chips(it.keywords, "acc")) : null, checkNote(it.check))));
      return aiPanel(task, body, res.items.map((it) => `- ${it.rewritten}`).join("\n"));
    }
    if (task === "summary" || task === "cover")
      return aiPanel(task, [h("p", { class: "ai-text" }, res.text), checkNote(res.check)], res.text);
    const qs = res.questions.map((q, i) => h("div", { class: "ai-q" }, h("b", {}, `${i + 1}. ${q.question}`),
      q.why ? h("p", {}, h("small", {}, "Por qué la preguntan: "), q.why) : null,
      q.tip ? h("p", {}, h("small", {}, "Cómo responder: "), q.tip) : null));
    return aiPanel(task, qs, res.questions.map((q, i) => `${i + 1}. ${q.question}\n   ${q.tip}`).join("\n\n"));
  }
  async function runAi(tasks) {
    const out = $("ai-out"), err = $("ai-error"), src = state.last;
    err.hidden = true;
    if (!$("ai-consent").checked) { err.textContent = "Marca la casilla de consentimiento para continuar."; err.hidden = false; return; }
    if (!src) { err.textContent = "Primero analiza un CV y una oferta."; err.hidden = false; return; }
    const fd = new FormData();
    fd.append("cv_file", src.cv);
    if (src.jobFile) fd.append("job_file", src.jobFile); else fd.append("job_text", src.job);
    fd.append("tasks", tasks.join(",")); fd.append("consent", "true");
    const buttons = document.querySelectorAll(".ai-btn");
    buttons.forEach((b) => { b.disabled = true; });
    const status = $("ai-status"); status.textContent = "La IA está escribiendo…";
    try {
      const data = await api("/api/v1/assist", { method: "POST", body: fd });
      for (const task of tasks) {
        const node = renderAi(task, data.results[task] || { error: "Sin respuesta." });
        const old = $(`ai-${task}`);
        if (old) old.replaceWith(node); else out.append(node);
      }
      status.textContent = "";
    } catch (e) {
      status.textContent = "";
      err.textContent = e.message; err.hidden = false;
    } finally { buttons.forEach((b) => { b.disabled = false; }); }
  }
  function cardAssistant() {
    const off = !(state.health && state.health.llm);
    const consent = h("input", { type: "checkbox", id: "ai-consent" });
    const btns = AI_TASKS.map(([k, ico, label]) => {
      const b = h("button", { class: "ghost ai-btn", type: "button", disabled: off }, `${ico} ${label}`);
      b.addEventListener("click", () => runAi([k]));
      return b;
    });
    const all = h("button", { class: "primary ai-btn", type: "button", disabled: off }, "Generar las 4");
    all.addEventListener("click", () => runAi(AI_TASKS.map((x) => x[0])));
    const body = h("div", {},
      h("p", { class: "sub", style: false }, off ? "La IA no está activa: define GROQ_API_KEY en el archivo .env y reinicia." :
        "Usa tu CV y esta oferta para escribir borradores. Solo reordena y redacta lo que ya está en tu CV: no inventa experiencia, y te avisa si menciona algo que no aparece en él."),
      h("label", { class: "chk ai-consent" }, consent, h("span", {}, "Entiendo que el texto de mi CV y de la oferta se enviará a Groq para generar esto. No se guarda.")),
      h("div", { class: "ai-btns" }, btns, all), h("p", { class: "sub", id: "ai-status", "aria-live": "polite" }),
      h("p", { class: "form-error", id: "ai-error", role: "alert", hidden: true }), h("div", { id: "ai-out" }));
    return card("🪄", "Asistente de IA", body, "span3");
  }

  function renderResults(r) {
    const root = $("results");
    clear(root);
    root.append(banner(r), h("div", { class: "dash" }, cardScore(r), cardRadar(r), cardStrengths(r), cardCategories(r),
      cardKeywords(r), cardTimeline(r), cardAts(r), cardUnderstood(r), cardRecs(r), cardAssistant()));
  }

  // ---------------------------------------------------------------- historial
  async function loadHistory() {
    const body = $("h-body");
    clear(body);
    body.append(h("p", { class: "muted" }, "Cargando…"));
    try {
      const items = await api("/api/v1/history");
      clear(body);
      if (!items.length) return body.append(h("div", { class: "empty" }, h("div", { class: "empty-art", "aria-hidden": "true" }, "🔁"),
        h("h2", {}, "Aún no has analizado ninguna oferta"), h("p", {}, "Cuando analices una, aparecerá aquí para que no la repitas.")));
      const rows = items.map((i) => {
        const tone = i.last_score >= 70 ? "ok" : i.last_score >= 50 ? "warn" : "bad";
        const del = h("button", { class: "ghost danger", type: "button", "aria-label": `Olvidar «${i.title}»` }, "Olvidar");
        del.addEventListener("click", async () => { try { await api(`/api/v1/history/${encodeURIComponent(i.id)}`, { method: "DELETE" }); } catch (e) { /* ya no existe */ } loadHistory(); });
        return h("tr", {}, h("td", {}, fmtDate(i.last_seen)), h("td", {}, i.title),
          h("td", { class: "num-c" }, h("span", { class: `pill ${tone}` }, num(i.last_score))), h("td", { class: "num-c" }, String(i.times)), h("td", {}, del));
      });
      body.append(h("div", { class: "tbl-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Última vez"), h("th", {}, "Oferta"),
        h("th", { class: "num-c" }, "Nota"), h("th", { class: "num-c" }, "Veces"), h("th", {}, ""))), h("tbody", {}, rows))));
    } catch (e) {
      clear(body); body.append(h("p", { class: "form-error" }, e.message));
    }
  }
  function initHistory() {
    $("h-refresh").addEventListener("click", loadHistory);
    const clr = $("h-clear");
    let armed = null;
    clr.addEventListener("click", async () => {
      if (!armed) { clr.textContent = "Pulsa de nuevo para confirmar"; armed = setTimeout(() => { armed = null; clr.textContent = "Vaciar historial"; }, 4000); return; }
      clearTimeout(armed); armed = null; clr.textContent = "Vaciar historial";
      try { await api("/api/v1/history", { method: "DELETE" }); } catch (e) { /* ignorar */ }
      loadHistory();
    });
  }

  // ---------------------------------------------------------------- cómo se calcula
  function renderHow() {
    const root = $("how-body");
    clear(root);
    const w = (state.health && state.health.weights) || { skills: .45, semantic: .2, experience: .15, education: .1, languages: .1 };
    const rows = Object.entries(w).map(([k, v]) => {
      const fill = h("i"); fill.style.width = `${Math.round(v * 100)}%`;
      return h("div", { class: "wrow" }, h("span", {}, `${COMP[k] ? COMP[k][0] + " " + COMP[k][1] : k}`),
        h("div", { class: "bar-t" }, fill), h("b", {}, `${Math.round(v * 100)} %`));
    });
    root.append(h("div", { class: "how" },
      h("h2", {}, "Una nota que puedes comprobar"),
      h("p", {}, "La nota global (0-100) es la suma ponderada de cinco bloques. Si la oferta no pide algo (por ejemplo, idiomas), ese bloque no cuenta y el peso se reparte entre los demás."),
      rows,
      h("h3", {}, "Qué hay detrás"),
      h("ul", {},
        h("li", {}, "Habilidades: se buscan en tu CV y en la oferta con un diccionario de tecnologías. Lo imprescindible pesa un 80 % y lo que «se valora», un 20 %."),
        h("li", {}, "Tener una alternativa vale: si la oferta pide «AWS o Azure» y tienes una, cuenta. Una tecnología de la misma familia da medio punto."),
        h("li", {}, "Afinidad: parecido global entre los textos del CV y de la oferta."),
        h("li", {}, "Experiencia, formación e idiomas: se comparan con lo que la oferta indica; si no indica nada, no penalizan."),
        h("li", {}, "El resumen con IA (Groq) solo recibe un extracto estructurado: notas y nombres de habilidades. Nunca el texto de tu CV ni de la oferta.")),
      h("h3", {}, "Privacidad"),
      h("p", {}, "El CV se procesa en memoria y se descarta. Del historial solo se guardan el título de la oferta, su huella, la fecha y la nota.")));
  }

  // ---------------------------------------------------------------- arranque
  function init() {
    initTheme(); initForm(); initHistory();
    document.querySelectorAll(".nav-btn").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
    $("burger").addEventListener("click", () => {
      const open = $("side").classList.toggle("is-open");
      $("burger").setAttribute("aria-expanded", String(open));
    });
    try { $("api-key").value = sessionStorage.getItem("cvm-key") || ""; } catch { /* ignorar */ }
    $("api-key").addEventListener("change", () => { try { sessionStorage.setItem("cvm-key", $("api-key").value); } catch { /* ignorar */ } });
    loadHealth();
  }
  init();
})();
