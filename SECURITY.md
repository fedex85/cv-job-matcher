# Seguridad

## Cómo informar de una vulnerabilidad

Abre un aviso privado desde la pestaña **Security → Report a vulnerability** del repositorio (o escribe al
mantenedor). Evita publicar el problema en un issue abierto hasta que esté corregido.

## Antes de subir cambios

- **Nunca** subas tu archivo `.env` ni tu clave de Groq (`GROQ_API_KEY`). Está en `.gitignore`; antes de cada
  `git push`, comprueba con `git status` que no aparece.
- No subas CVs reales ni ofertas con datos personales (`data/raw/` y `data/processed/` están ignorados).
- Si una clave se sube por error, **revócala** en <https://console.groq.com/keys> y crea otra: borrar el
  archivo del historial de git no es suficiente.
