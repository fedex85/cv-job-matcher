"""Cliente mínimo de Groq (API compatible con OpenAI) usando httpx.

Se usa httpx directamente para no añadir otro SDK: menos dependencias y es
trivial de simular en los tests con httpx.MockTransport."""

from __future__ import annotations

import time

import httpx

from src.utils.logger import get_logger

log = get_logger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_RETRY_STATUS = {429, 500, 502, 503, 504}


class LLMError(Exception):
    """Fallo del proveedor LLM. El mensaje es seguro para mostrar al usuario."""


class GroqClient:
    def __init__(self, api_key: str, model: str, timeout: float = 30.0, *, max_retries: int = 2,
                 base_url: str = GROQ_BASE_URL, transport: httpx.BaseTransport | None = None) -> None:
        if not api_key:
            raise LLMError("Falta GROQ_API_KEY.")
        self._model = model
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    def chat_json(self, system: str, user: str, *, max_tokens: int = 700, temperature: float = 0.3) -> str:
        """Devuelve el contenido (JSON en texto) de la respuesta del modelo."""
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        last = "error desconocido"
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                last = type(exc).__name__
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, ValueError) as exc:
                        raise LLMError("Respuesta inesperada del proveedor LLM.") from exc
                if resp.status_code in (401, 403):
                    raise LLMError("La clave de Groq no es válida o no tiene permisos.")
                last = f"HTTP {resp.status_code}"
                if resp.status_code not in _RETRY_STATUS:
                    break
            if attempt < self._max_retries:
                time.sleep(min(2 ** attempt * 0.5, 4))
        log.warning("Groq no disponible tras reintentos: %s", last)
        raise LLMError("El servicio de IA no está disponible ahora mismo.")

    def close(self) -> None:
        self._client.close()
