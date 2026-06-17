"""
config/config.py
------------------
Carga la configuración del proyecto desde el archivo .env (en la raíz).

Reglas:
- NUNCA imprime claves completas. Usa mask() para mostrarlas ofuscadas.
- Si .env no existe, usa valores por defecto seguros.
- Todas las rutas se calculan relativas a la raíz del proyecto.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# --- Rutas base -------------------------------------------------------------
# config/ está dentro de la raíz, así que la raíz es el padre de este archivo.
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"

if load_dotenv is not None and ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# Carpetas del proyecto
OUTPUTS_DIR = ROOT_DIR / "outputs"
IDEAS_DIR = OUTPUTS_DIR / "ideas"
SCRIPTS_OUT_DIR = OUTPUTS_DIR / "scripts"
AUDIO_DIR = OUTPUTS_DIR / "audio"
IMAGES_DIR = OUTPUTS_DIR / "images"
VIDEOS_DIR = OUTPUTS_DIR / "videos"
PROMPTS_DIR = ROOT_DIR / "prompts"
DATABASE_DIR = ROOT_DIR / "database"
LOGS_DIR = ROOT_DIR / "logs"


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# --- n8n --------------------------------------------------------------------
N8N_PORT = _get("N8N_PORT", "5678")
N8N_HOST = _get("N8N_HOST", "localhost")
N8N_PROTOCOL = _get("N8N_PROTOCOL", "http")
N8N_URL = f"{N8N_PROTOCOL}://{N8N_HOST}:{N8N_PORT}"

def _localize(url: str) -> str:
    """
    Los scripts de Python corren SIEMPRE en el host (no dentro del contenedor
    de n8n). 'host.docker.internal' solo resuelve dentro de Docker, así que para
    estos scripts lo convertimos a 'localhost'. n8n sigue usando el valor del
    .env tal cual desde sus nodos HTTP.
    """
    return url.replace("host.docker.internal", "localhost")


# --- Ollama -----------------------------------------------------------------
OLLAMA_BASE_URL = _localize(_get("OLLAMA_BASE_URL", "http://localhost:11434"))
OLLAMA_MODEL = _get("OLLAMA_MODEL", "llama3.1:8b")

# --- ComfyUI ----------------------------------------------------------------
COMFYUI_URL = _localize(_get("COMFYUI_URL", "http://localhost:8188"))
# Checkpoint instalado en ComfyUI/models/checkpoints (cámbialo al tuyo).
COMFYUI_CKPT = _get("COMFYUI_CKPT", "sd_xl_base_1.0.safetensors")
# Dimensiones de generación (vertical). El video luego escala/rellena a VIDEO_*.
COMFYUI_IMG_WIDTH = int(_get("COMFYUI_IMG_WIDTH", "832") or 832)
COMFYUI_IMG_HEIGHT = int(_get("COMFYUI_IMG_HEIGHT", "1216") or 1216)
COMFYUI_NEG = _get("COMFYUI_NEG", "lowres, blurry, watermark, text, deformed, ugly")

# --- Telegram ---------------------------------------------------------------
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")

# --- Audio ------------------------------------------------------------------
TTS_PROVIDER = _get("TTS_PROVIDER", "edge")
EDGE_TTS_VOICE = _get("EDGE_TTS_VOICE", "es-MX-DaliaNeural")
ELEVENLABS_API_KEY = _get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = _get("ELEVENLABS_VOICE_ID")

# --- Proveedores opcionales -------------------------------------------------
OPENAI_API_KEY = _get("OPENAI_API_KEY")
DEEPSEEK_API_KEY = _get("DEEPSEEK_API_KEY")
GEMINI_API_KEY = _get("GEMINI_API_KEY")

# --- Video ------------------------------------------------------------------
VIDEO_WIDTH = int(_get("VIDEO_WIDTH", "1080") or 1080)
VIDEO_HEIGHT = int(_get("VIDEO_HEIGHT", "1920") or 1920)
VIDEO_FPS = int(_get("VIDEO_FPS", "30") or 30)
SCENE_DURATION = int(_get("SCENE_DURATION", "5") or 5)


def mask(value: str) -> str:
    """Devuelve una versión ofuscada de un secreto para mostrar en logs."""
    if not value:
        return "(vacío)"
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***{value[-2:]}"


def summary() -> str:
    """Resumen legible de la configuración SIN exponer claves completas."""
    lines = [
        "Configuración cargada:",
        f"  Raíz proyecto : {ROOT_DIR}",
        f"  .env presente : {'sí' if ENV_FILE.exists() else 'NO'}",
        f"  n8n           : {N8N_URL}",
        f"  Ollama        : {OLLAMA_BASE_URL} (modelo: {OLLAMA_MODEL})",
        f"  ComfyUI       : {COMFYUI_URL}",
        f"  Telegram bot  : {mask(TELEGRAM_BOT_TOKEN)}",
        f"  Telegram chat : {mask(TELEGRAM_CHAT_ID)}",
        f"  TTS           : {TTS_PROVIDER} (voz: {EDGE_TTS_VOICE})",
        f"  ElevenLabs    : {mask(ELEVENLABS_API_KEY)}",
        f"  Video         : {VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {VIDEO_FPS}fps",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
