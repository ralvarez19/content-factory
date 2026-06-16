"""
scripts/utils.py
----------------
Funciones auxiliares compartidas por todos los scripts:
- Acceso a la configuración (añade la raíz al sys.path).
- Generación de rutas ordenadas por fecha y tema.
- Logging sencillo a consola + archivo en logs/.
- Cliente mínimo de Ollama (texto).
- Cliente mínimo de Telegram (notificación / aprobación).

Sin dependencias externas más allá de "requests" y "python-dotenv".
"""

from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# --- Hacer importable el paquete config -------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import config  # noqa: E402

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


# --- Logging ----------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    """Logger que escribe a consola y a logs/content-factory.log."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            "%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(config.LOGS_DIR / "content-factory.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


log = get_logger("content-factory")


# --- Utilidades de texto / rutas --------------------------------------------
def slugify(text: str, max_len: int = 50) -> str:
    """Convierte un tema en un nombre de carpeta seguro: 'Mi Idea!' -> 'mi-idea'."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:max_len].strip("-") or "sin-tema"


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def project_path(*parts: str) -> Path:
    """Construye una ruta dentro del proyecto y crea los directorios padre."""
    p = config.ROOT_DIR.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def output_dir(kind: str, theme: str) -> Path:
    """
    Devuelve una carpeta ordenada por fecha y tema, p.ej.:
      outputs/videos/2026-06-16_mi-tema/
    'kind' es uno de: ideas, scripts, audio, images, videos.
    """
    folder = config.OUTPUTS_DIR / kind / f"{today_str()}_{slugify(theme)}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_json(path: Path, default=None):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- Cliente Ollama ---------------------------------------------------------
def ollama_available() -> bool:
    if requests is None:
        return False
    try:
        r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def ollama_generate(prompt: str, model: str | None = None,
                    temperature: float = 0.8, timeout: int = 180) -> str:
    """Genera texto con Ollama (no streaming). Lanza excepción si falla."""
    if requests is None:
        raise RuntimeError("Falta la librería 'requests' (pip install requests).")
    model = model or config.OLLAMA_MODEL
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    r = requests.post(f"{config.OLLAMA_BASE_URL}/api/generate",
                      json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "").strip()


# --- Cliente Telegram -------------------------------------------------------
def telegram_configured() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


def telegram_send(text: str, silent: bool = False) -> bool:
    """Envía un mensaje de texto al chat configurado. Devuelve True si tuvo éxito."""
    if requests is None or not telegram_configured():
        log.warning("Telegram no configurado; mensaje no enviado.")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": silent,
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        ok = r.status_code == 200
        if not ok:
            log.error("Telegram error %s: %s", r.status_code, r.text[:200])
        return ok
    except Exception as e:  # pragma: no cover
        log.error("Telegram excepción: %s", e)
        return False


def telegram_send_document(file_path: Path, caption: str = "") -> bool:
    """Envía un archivo (video/imagen/doc) a Telegram."""
    if requests is None or not telegram_configured():
        log.warning("Telegram no configurado; documento no enviado.")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            r = requests.post(url,
                              data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption},
                              files={"document": f}, timeout=120)
        return r.status_code == 200
    except Exception as e:  # pragma: no cover
        log.error("Telegram doc excepción: %s", e)
        return False


def read_prompt_template(name: str) -> str:
    """Lee una plantilla de prompts/<name>. Devuelve '' si no existe."""
    p = config.PROMPTS_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else ""
