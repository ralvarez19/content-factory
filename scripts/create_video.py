"""
scripts/create_video.py
-----------------------
Pasos 7-11 del flujo: a partir del guion, prepara audio narrado, prepara
imagenes (ComfyUI si esta disponible, o placeholders con los prompts listos)
y ensambla el video final con FFmpeg. Guarda todo por fecha/tema y avisa por
Telegram.

Uso:
    python scripts/create_video.py --tema "finanzas personales"
    python scripts/create_video.py --guion "outputs/scripts/2026-06-16_finanzas/guion.json"

Estrategia semiautomatica:
- Audio: edge-tts (gratuito, local). Si falla, escenas con duracion fija.
- Imagenes: si ComfyUI responde, las genera con config/comfyui_workflow.json;
  si no, crea placeholders con el texto del prompt para reemplazar a mano.
- Video: FFmpeg (requerido). MoviePy es alternativa opcional.
"""

from __future__ import annotations

import argparse
import asyncio
import json as _json
import random as _random
import shutil
import subprocess
import sys
import time as _time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import config  # noqa: E402
import utils  # noqa: E402


# --------------------------------------------------------------------------
def find_guion(tema, guion_path):
    if guion_path:
        p = Path(guion_path)
        return p if p.is_absolute() else config.ROOT_DIR / p
    folder = config.SCRIPTS_OUT_DIR / (utils.today_str() + "_" + utils.slugify(tema))
    p = folder / "guion.json"
    if p.exists():
        return p
    matches = sorted(config.SCRIPTS_OUT_DIR.glob("*_" + utils.slugify(tema) + "/guion.json"))
    if matches:
        return matches[-1]
    raise FileNotFoundError("No encuentro guion.json para '%s'. Genera el guion primero." % tema)


# --- AUDIO (edge-tts) -----------------------------------------------------
async def _tts_edge(text, out_file):
    try:
        import edge_tts
    except ImportError:
        utils.log.warning("edge-tts no instalado (pip install edge-tts). Sin audio.")
        return False
    try:
        communicate = edge_tts.Communicate(text, config.EDGE_TTS_VOICE)
        await communicate.save(str(out_file))
        return out_file.exists() and out_file.stat().st_size > 0
    except Exception as e:
        utils.log.error("Fallo edge-tts: %s", e)
        return False


def generate_audio(escenas, audio_dir):
    audios = []
    for e in escenas:
        num = e.get("numero", len(audios) + 1)
        text = (e.get("narracion") or "").strip()
        out = audio_dir / ("escena_%02d.mp3" % num)
        if text and asyncio.run(_tts_edge(text, out)):
            audios.append(out)
            utils.log.info("Audio escena %s -> %s", num, out.name)
        else:
            audios.append(None)
    return audios


def audio_duration(path):
    """Duracion en segundos via ffprobe; 0 si falla."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path or not Path(path).exists():
        return 0.0
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip() or 0)
    except Exception:
        return 0.0


# --- IMAGENES: placeholder -------------------------------------------------
def _placeholder_image(prompt, out_file, idx):
    """Crea una imagen vertical con el texto del prompt (fallback manual)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        utils.log.warning("Pillow no instalado; no se crean placeholders.")
        return False
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    palette = [(30, 30, 46), (40, 30, 60), (20, 40, 55), (50, 35, 35)]
    img = Image.new("RGB", (w, h), palette[idx % len(palette)])
    d = ImageDraw.Draw(img)
    d.text((60, 80), "ESCENA " + str(idx + 1), fill=(255, 255, 255))
    words = prompt.split()
    line, y = "", 200
    for word in words:
        if len(line) + len(word) > 40:
            d.text((60, y), line, fill=(210, 210, 220))
            y += 40
            line = word + " "
        else:
            line += word + " "
    d.text((60, y), line, fill=(210, 210, 220))
    d.text((60, h - 120), "[ Placeholder - reemplaza con tu imagen ]", fill=(255, 180, 120))
    img.save(out_file)
    return True


# --- IMAGENES: ComfyUI -----------------------------------------------------
_COMFY_CLIENT_ID = "content-factory-" + utils.timestamp()


def _comfy_alive():
    try:
        return utils.requests.get(config.COMFYUI_URL + "/system_stats", timeout=5).status_code == 200
    except Exception:
        return False


def _load_comfy_workflow(prompt):
    """Carga la plantilla de workflow y sustituye los marcadores."""
    wf_path = config.ROOT_DIR / "config" / "comfyui_workflow.json"
    if not wf_path.exists():
        return None
    raw = wf_path.read_text(encoding="utf-8")
    safe_prompt = _json.dumps(prompt)[1:-1]
    safe_neg = _json.dumps(config.COMFYUI_NEG)[1:-1]
    raw = raw.replace("__PROMPT__", safe_prompt)
    raw = raw.replace("__NEG__", safe_neg)
    raw = raw.replace("__CKPT__", config.COMFYUI_CKPT)
    raw = raw.replace('"__SEED__"', str(_random.randint(1, 2000000000)))
    raw = raw.replace('"__WIDTH__"', str(config.COMFYUI_IMG_WIDTH))
    raw = raw.replace('"__HEIGHT__"', str(config.COMFYUI_IMG_HEIGHT))
    try:
        wf = _json.loads(raw)
        wf.pop("_comment", None)
        return wf
    except Exception as e:
        utils.log.error("Workflow ComfyUI invalido tras sustituir: %s", e)
        return None


def _comfy_generate(prompt, out_file, timeout=180):
    """
    Genera una imagen con ComfyUI:
      1) POST /prompt con el workflow (formato API).
      2) Sondea /history/<prompt_id> hasta que termina.
      3) Descarga la imagen via /view y la guarda en out_file.
    Devuelve False ante cualquier fallo (el llamador usa placeholder).
    """
    wf = _load_comfy_workflow(prompt)
    if wf is None:
        return False
    req = utils.requests
    try:
        r = req.post(config.COMFYUI_URL + "/prompt",
                     json={"prompt": wf, "client_id": _COMFY_CLIENT_ID}, timeout=30)
        if r.status_code != 200:
            utils.log.error("ComfyUI /prompt %s: %s", r.status_code, r.text[:200])
            return False
        prompt_id = r.json().get("prompt_id")
        if not prompt_id:
            return False

        deadline = _time.time() + timeout
        history = None
        while _time.time() < deadline:
            h = req.get(config.COMFYUI_URL + "/history/" + str(prompt_id), timeout=15)
            if h.status_code == 200 and h.json().get(prompt_id):
                history = h.json()[prompt_id]
                break
            _time.sleep(1.5)
        if not history:
            utils.log.error("ComfyUI: timeout esperando la imagen.")
            return False

        for node_out in history.get("outputs", {}).values():
            for img in node_out.get("images", []):
                params = {
                    "filename": img.get("filename"),
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                }
                v = req.get(config.COMFYUI_URL + "/view", params=params, timeout=30)
                if v.status_code == 200 and v.content:
                    out_file.write_bytes(v.content)
                    utils.log.info("ComfyUI genero %s", out_file.name)
                    return True
        return False
    except Exception as e:
        utils.log.error("ComfyUI excepcion: %s", e)
        return False


def prepare_images(escenas, images_dir):
    """ComfyUI si esta disponible; si no, placeholders + prompts listos."""
    comfy_ok = utils.requests is not None and _comfy_alive()
    images = []
    for i, e in enumerate(escenas):
        num = e.get("numero", i + 1)
        prompt = e.get("prompt_imagen", "")
        out = images_dir / ("escena_%02d.png" % num)
        done = False
        if comfy_ok:
            done = _comfy_generate(prompt, out)
        if not done:
            done = _placeholder_image(prompt, out, i)
        images.append(out if done else None)
    if not comfy_ok:
        utils.log.warning("ComfyUI no disponible: se crearon placeholders. "
                          "Prompts en images_dir/prompts.txt para generacion manual.")
        lineas = []
        for i, e in enumerate(escenas):
            lineas.append("Escena " + str(e.get("numero", i + 1)) + ": " + e.get("prompt_imagen", ""))
        (images_dir / "prompts.txt").write_text(chr(10).join(lineas), encoding="utf-8")
    return images


# --- VIDEO (FFmpeg, concatenacion por TS) ---------------------------------
def build_video(escenas, images, audios, out_file):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        utils.log.error("FFmpeg no esta en el PATH; no se puede ensamblar el video.")
        return False

    work = out_file.parent / "_clips"
    work.mkdir(exist_ok=True)
    ts_clips = []

    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1") % (
        config.VIDEO_WIDTH, config.VIDEO_HEIGHT,
        config.VIDEO_WIDTH, config.VIDEO_HEIGHT)

    for i, e in enumerate(escenas):
        img = images[i]
        aud = audios[i]
        if img is None:
            continue
        dur = audio_duration(aud) if aud else 0.0
        if dur <= 0:
            dur = float(e.get("duracion_seg", config.SCENE_DURATION))
        ts = work / ("clip_%02d.ts" % i)
        cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(img)]
        if aud:
            cmd += ["-i", str(aud)]
        cmd += ["-c:v", "libx264", "-t", "%.2f" % dur, "-pix_fmt", "yuv420p",
                "-vf", vf, "-r", str(config.VIDEO_FPS)]
        if aud:
            cmd += ["-c:a", "aac", "-shortest"]
        cmd += ["-f", "mpegts", str(ts)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            ts_clips.append(ts)
        else:
            utils.log.error("FFmpeg fallo en escena %d: %s", i + 1, r.stderr[-300:])

    if not ts_clips:
        utils.log.error("No se genero ningun clip.")
        return False

    # Concatenacion por protocolo (sin archivo de lista, evita comillas/saltos).
    concat_arg = "concat:" + "|".join(t.as_posix() for t in ts_clips)
    cmd = [ffmpeg, "-y", "-i", concat_arg, "-c", "copy",
           "-bsf:a", "aac_adtstoasc", str(out_file)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and out_file.exists()
    if not ok:
        # reintento recodificando
        cmd = [ffmpeg, "-y", "-i", concat_arg, "-c:v", "libx264",
               "-c:a", "aac", "-pix_fmt", "yuv420p", str(out_file)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = r.returncode == 0 and out_file.exists()
    if not ok:
        utils.log.error("Concatenacion fallo: %s", r.stderr[-300:])
    try:
        shutil.rmtree(work)
    except Exception:
        pass
    return ok


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Arma el video final desde el guion.")
    ap.add_argument("--tema", help="Tema usado en el guion.")
    ap.add_argument("--guion", help="Ruta directa a guion.json.")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    if not args.tema and not args.guion:
        ap.error("Indica --tema o --guion.")

    guion_path = find_guion(args.tema, args.guion)
    guion = utils.load_json(guion_path)
    escenas = guion.get("escenas", [])
    tema = args.tema or guion.get("titulo", "tema")
    if not escenas:
        utils.log.error("El guion no tiene escenas.")
        return 1

    video_dir = utils.output_dir("videos", tema)
    audio_dir = utils.output_dir("audio", tema)
    images_dir = utils.output_dir("images", tema)

    utils.log.info("1/3 Generando audio...")
    audios = generate_audio(escenas, audio_dir)
    utils.log.info("2/3 Preparando imagenes...")
    images = prepare_images(escenas, images_dir)
    utils.log.info("3/3 Ensamblando video con FFmpeg...")

    out_file = video_dir / "final.mp4"
    ok = build_video(escenas, images, audios, out_file)

    if ok:
        utils.log.info("Video listo: %s", out_file)
        if not args.no_telegram and utils.telegram_configured():
            sent = utils.telegram_send_document(out_file, caption="Video listo: " + str(tema))
            if not sent:
                utils.telegram_send("Video listo (muy grande para enviar): " + str(out_file))
        print("\n=== VIDEO GENERADO ===\n" + str(out_file))
        return 0

    utils.log.error("No se pudo generar el video.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
