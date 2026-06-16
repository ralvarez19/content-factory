"""
scripts/check_services.py
-------------------------
Verifica que los servicios necesarios estén disponibles antes de operar:
  - Ollama (texto)        : http://localhost:11434
  - ComfyUI (imágenes)    : http://localhost:8188   (opcional)
  - n8n (orquestación)    : http://localhost:5678    (opcional)
  - FFmpeg (video)        : binario en PATH
  - Telegram              : configuración en .env

Uso:
    python scripts/check_services.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import config  # noqa: E402

try:
    import requests
except ImportError:
    requests = None

OK = "[ OK ]"
FAIL = "[FALLA]"
WARN = "[AVISO]"


def _http_ok(url: str, timeout: int = 5) -> bool:
    if requests is None:
        return False
    try:
        return requests.get(url, timeout=timeout).status_code < 500
    except Exception:
        return False


def check_ollama() -> bool:
    if requests is None:
        print(f"{FAIL} Ollama: falta 'requests' (pip install requests)")
        return False
    try:
        r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code != 200:
            print(f"{FAIL} Ollama no responde en {config.OLLAMA_BASE_URL}")
            return False
        models = [m.get("name", "") for m in r.json().get("models", [])]
        if not models:
            print(f"{WARN} Ollama activo pero SIN modelos. Ejecuta: ollama pull {config.OLLAMA_MODEL}")
            return False
        target = config.OLLAMA_MODEL
        has_target = any(target.split(":")[0] in m for m in models)
        mark = OK if has_target else WARN
        print(f"{mark} Ollama activo. Modelos: {', '.join(models)}")
        if not has_target:
            print(f"       Falta el modelo configurado '{target}'. Ejecuta: ollama pull {target}")
        return has_target
    except Exception as e:
        print(f"{FAIL} Ollama: {e}")
        return False


def check_comfyui() -> bool:
    if _http_ok(config.COMFYUI_URL):
        print(f"{OK} ComfyUI activo en {config.COMFYUI_URL}")
        return True
    print(f"{WARN} ComfyUI no responde en {config.COMFYUI_URL} (opcional; se usará fallback de prompts).")
    return False


def check_n8n() -> bool:
    if _http_ok(config.N8N_URL):
        print(f"{OK} n8n activo en {config.N8N_URL}")
        return True
    print(f"{WARN} n8n no responde en {config.N8N_URL}. ¿Está Docker corriendo? -> docker compose up -d")
    return False


def check_ffmpeg() -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        print(f"{FAIL} FFmpeg no está en el PATH.")
        return False
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10)
        first = out.stdout.splitlines()[0] if out.stdout else "ffmpeg"
        print(f"{OK} {first}")
        return True
    except Exception as e:
        print(f"{WARN} FFmpeg encontrado pero falló al ejecutar: {e}")
        return False


def check_telegram() -> bool:
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        print(f"{OK} Telegram configurado (token {config.mask(config.TELEGRAM_BOT_TOKEN)}).")
        return True
    print(f"{WARN} Telegram sin configurar (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en .env).")
    return False


def main() -> int:
    print("=" * 60)
    print(" CONTENT FACTORY - Verificación de servicios")
    print("=" * 60)
    print(config.summary())
    print("-" * 60)

    results = {
        "Ollama (requerido)": check_ollama(),
        "FFmpeg (requerido)": check_ffmpeg(),
        "ComfyUI (opcional)": check_comfyui(),
        "n8n (opcional)": check_n8n(),
        "Telegram (recomendado)": check_telegram(),
    }
    print("-" * 60)
    required_ok = results["Ollama (requerido)"] and results["FFmpeg (requerido)"]
    if required_ok:
        print(f"{OK} Servicios requeridos listos. Puedes generar contenido.")
    else:
        print(f"{FAIL} Faltan servicios requeridos (Ollama y/o FFmpeg).")
    print("=" * 60)
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
