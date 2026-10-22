"""Interfaz web (Gradio). Usa el mismo pipeline y las mismas validaciones que la API.

Compatibilidad: Gradio 6 recibe ``css`` y ``theme`` al montar la app; versiones anteriores
los reciben en ``gr.Blocks``. ``build_ui`` detecta cuál toca y deja los parámetros pendientes
en ``ui.cvm_mount_kwargs`` para que ``app.api`` los pase a ``mount_gradio_app``.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import gradio as gr

from src.config import Settings
from src.ingestion import IngestionError, load_document
from src.pipeline import AnalysisPipeline
from src.utils.logger import get_logger

from .components import (
    CSS,
    EXAMPLE_JOB,
    FORCE_DARK_JS,
    HISTORY_HEADERS,
    empty_state,
    error_html,
    hero_html,
    history_rows,
    render_results,
    step_html,
)

log = get_logger(__name__)
MIN_JOB_CHARS = 40


def _theme():
    try:
        return gr.themes.Soft(primary_hue="indigo", secondary_hue="teal", neutral_hue="slate")
    except Exception:  # pragma: no cover - el tema es opcional
        return None


def build_ui(pipeline: AnalysisPipeline, settings: Settings) -> gr.Blocks:
    def history_table() -> list[list]:
        return history_rows(pipeline.history.list())

    def run(cv_path: str | None, job_text: str, job_path: str | None, use_llm: bool, remember: bool):
        try:
            if not cv_path:
                raise IngestionError("cv_missing", "Sube tu CV (PDF, DOCX o TXT).")
            cv = load_document(Path(cv_path).name, Path(cv_path).read_bytes(), settings)
            if job_path:
                job = load_document(Path(job_path).name, Path(job_path).read_bytes(), settings).text
            else:
                job = (job_text or "").strip()
            if len(job) < MIN_JOB_CHARS:
                raise IngestionError("job_short", "Pega el texto de la oferta (mínimo ~40 caracteres) o sube un archivo.")
            if len(job) > settings.max_job_chars:
                raise IngestionError("job_long", f"La oferta supera los {settings.max_job_chars} caracteres.")
            result = pipeline.analyze(cv.text, job, bool(use_llm), bool(remember))
        except IngestionError as exc:
            gr.Warning(exc.message)
            return error_html(exc.message), history_table()
        except Exception:
            log.exception("Error inesperado en la UI")
            gr.Warning("Error interno al analizar. Inténtalo de nuevo.")
            return error_html("Error interno al analizar. Inténtalo de nuevo."), history_table()
        return render_results(result), history_table()

    def clear_history():
        removed = pipeline.history.clear()
        gr.Info(f"Historial vaciado ({removed} ofertas).")
        return history_table()

    params = inspect.signature(gr.Blocks.__init__).parameters
    blocks_kwargs: dict = {"title": "CV Matcher"}
    mount_kwargs: dict = {}
    for key, value in (("css", CSS), ("theme", _theme()), ("js", FORCE_DARK_JS)):
        if value is not None:
            (blocks_kwargs if key in params else mount_kwargs)[key] = value

    with gr.Blocks(**blocks_kwargs) as ui:
        gr.HTML(hero_html())
        with gr.Tabs():
            with gr.Tab("🎯 Analizar"):
                with gr.Row():
                    with gr.Column(scale=4, min_width=320, elem_classes="cvm-panel"):
                        gr.HTML(step_html(1, "Sube tu CV", "PDF, DOCX o TXT · máximo "
                                          f"{settings.max_upload_mb} MB · no se guarda"))
                        cv_file = gr.File(label="Tu CV", file_types=[".pdf", ".docx", ".txt"], type="filepath")
                        gr.HTML(step_html(2, "Pega la oferta de empleo",
                                          "Copia el texto completo del anuncio, con sus requisitos"))
                        job_text = gr.Textbox(label="Oferta", lines=9, max_length=settings.max_job_chars,
                                              placeholder="Pega aquí el anuncio de trabajo…", show_label=False)
                        example_btn = gr.Button("✨ Probar con una oferta de ejemplo", size="sm", variant="secondary")
                        with gr.Accordion("…o sube la oferta como archivo", open=False):
                            job_file = gr.File(label="Oferta (PDF, DOCX o TXT)",
                                               file_types=[".pdf", ".docx", ".txt"], type="filepath")
                        gr.HTML(step_html(3, "Analiza"))
                        use_llm = gr.Checkbox(label="Consejos con IA (Groq)", value=settings.llm_available,
                                              interactive=settings.llm_available,
                                              info=None if settings.llm_available
                                              else "Define GROQ_API_KEY en .env para activarlo")
                        remember = gr.Checkbox(label="Recordar esta oferta (avisarme si la vuelvo a analizar)",
                                               value=settings.history_enabled,
                                               interactive=settings.history_enabled)
                        analyze_btn = gr.Button("Analizar mi CV", variant="primary", size="lg")
                    with gr.Column(scale=8, min_width=320):
                        results = gr.HTML(empty_state())
            with gr.Tab("🔁 Ofertas vistas"):
                gr.Markdown("Aquí quedan las ofertas que ya analizaste, para que no repitas trabajo. "
                            "**Solo se guarda la oferta** (título, nota y fecha), nunca tu CV.")
                table = gr.Dataframe(value=history_table, headers=HISTORY_HEADERS,
                                     datatype=["str", "str", "number", "number"], interactive=False, wrap=True)
                with gr.Row():
                    refresh_btn = gr.Button("Actualizar", size="sm")
                    clear_btn = gr.Button("🗑️ Vaciar historial", size="sm", variant="stop")
        gr.HTML("<div class='cvm'><p class='cvm-foot'>Tu CV se procesa en memoria y se descarta al terminar.</p></div>")

        example_btn.click(lambda: EXAMPLE_JOB, None, job_text, api_name=False)
        analyze_btn.click(run, [cv_file, job_text, job_file, use_llm, remember], [results, table],
                          api_name=False)
        refresh_btn.click(history_table, None, table, api_name=False)
        clear_btn.click(clear_history, None, table, api_name=False)
        ui.load(history_table, None, table, api_name=False)

    ui.cvm_mount_kwargs = mount_kwargs  # type: ignore[attr-defined]
    return ui
