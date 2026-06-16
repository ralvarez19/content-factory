"""
scripts/create_video.py
-----------------------
Pasos 7-11 del flujo: a partir del guion, prepara audio narrado, prepara
imágenes (ComfyUI si está disponible, o placeholders con los prompts listos)
y ensambla el video final con FFmpeg. Guarda todo por fecha/tema y avisa por
Telegram.

Uso:
    python scripts/create_video.py --tema "finanzas personales"
    python scripts/create_video.py --guion "outputs/scripts/2026-06-16_finanzas/guion.json"

Estrategia semiautomática:
- Audio: edge-tts (gratuito, local). Si falla, escenas con duración fija.
- Imágenes: si ComfyUI responde y hay workflow, las genera; si no, crea
  placeholders con el texto del prompt para que el usuario los reemplace.
- Video: FFmpeg (requerido). MoviePy es alternativa opcional.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import config  # noqa: E402
import utils  # noqa: E402


# --------------------------------------------------------------------------
def find_guion(tema: str | None, guion_path: str | None) -> Path:
    if guion_path:
        p = Path(guion_path)
        return p if p.is_absolute() else config.ROOT_DIR / p
    folder = config.SCRIPTS_OUT_DIR / f"{utils.today_str()}_{utils.slugify(tema)}"
    p = folder / "guion.json"
    if p.exists():
        return p
    matches = sorted(config.SCRIPTS_OUT_DIR.glob(f"*_{utils.slugify(tema)}/guion.json"))
    if matches:
        return matches[-1]
    raise FileNotFoundError(f"No encuentro guion.json para '{tema}'. Genera el guion primero.")


# --- AUDIO (edge-tts) -----------------------------------------------------
async def _tts_edge(text: str, out_file: Path) -> bool:
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


def generate_audio(escenas: list[dict], audio_dir: Path) -> list[Path | None]:
    audios: list[Path | None] = []
    for e in escenas:
        num = e.get("numero", len(audios) + 1)
        text = (e.get("narracion") or "").strip()
        out = audio_dir / f"escena_{num:02d}.mp3"
        if text and asyncio.run(_tts_edge(text, out)):
            audios.append(out)
            utils.log.info("Audio escena %s -> %s", num, out.name)
        else:
            audios.append(None)
    return audios


def audio_duration(path: Path) -> float:
    """Duración en segundos vía ffprobe; 0 si falla."""
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


# --- IMAGENES -------------------------------------------------------------
def _placeholder_image(prompt: str, out_file: Path, idx: int) -> bool:
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
    title = f"ESCENA {idx + 1}"
    d.text((60, 80), title, fill=(255, 255, 255))
    # Texto del prompt envuelto
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


def prepare_images(escenas: list[dict], images_dir: Path) -> list[Path | None]:
    """ComfyUI si está disponible; si no, placeholders + prompts listos."""
    comfy_ok = utils.requests is not None and _comfy_alive()
    images: list[Path | None] = []
    for i, e in enumerate(escenas):
        num = e.get("numero", i + 1)
        prompt = e.get("prompt_imagen", "")
        out = images_dir / f"escena_{num:02d}.png"
        done = False
        if comfy_ok:
            done = _comfy_generate(prompt, out)
        if not done:
            done = _placeholder_image(prompt, out, i)
        images.append(out if done else None)
    if not comfy_ok:
        utils.log.warning("ComfyUI no disponible: se crearon placeholders. "
                          "Prompts en images_dir/prompts.txt para generación manual.")
        (images_dir / "prompts.txt").write_text(
            "\n".join(f"Escena {e.get('numero', i+1)}: {e.get('prompt_imagen','')}"
                      for i, e in enumerate(escenas)), encoding="utf-8")
    return images


def _comfy_alive() -> bool:
    try:
        return utils.requests.get(f"{config.COMFYUI_URL}/system_stats", timeout=5).status_code == 200
    except Exception:
        return False


def _comfy_generate(prompt: str, out_file: Path) -> bool:
    """
    Hook para ComfyUI. Requiere un workflow API en config/comfyui_workflow.json
    con un nodo de texto positivo. Implementación mínima/segura: si no hay
    workflow, devuelve False para usar el fallback de placeholder.
    """
    wf_path = config.ROOT_DIR / "config" / "comfyui_workflow.json"
    if not wf_path.exists():
        return False
    # Implementación real del envío a /prompt se deja como mejora futura.
    utils.log.info("ComfyUI disponible; integración de workflow pendiente (usa fallback).")
    return False


# --- VIDEO (FFmpeg) -------------------------------------------------------
def build_video(escenas, images, audios, out_file: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        utils.log.error("FFmpeg no está en el PATH; no se puede ensamblar el video.")
        return False

    work = out_file.parent / "_clips"
    work.mkdir(exist_ok=True)
    clips: list[Path] = []

    for i, e in enumerate(escenas):
        img = images[i]
        aud = audios[i]
        if img is None:
            continue
        dur = audio_duration(aud) if aud else 0.0
        if dur <= 0:
            dur = float(e.get("duracion_seg", config.SCENE_DURATION))
        clip = work / f"clip_{i:02d}.mp4"
        cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(img)]
        if aud:
            cmd += ["-i", str(aud)]
        cmd += [
            "-c:v", "libx264", "-t", f"{dur:.2f}", "-pix_fmt", "yuv420p",
            "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
                   f"pad={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", str(config.VIDEO_FPS),
        ]
        if aud:
            cmd += ["-c:a", "aac", "-shortest"]
        cmd += [str(clip)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            clips.append(clip)
        else:
            utils.log.error("FFmpeg falló en escena %d: %s", i + 1, r.stderr[-300:])

    if not clips:
        utils.log.error("No se generó ningún clip.")
        return False

    # Concatenar
    list_file = work / "concat.txt"
    list_file.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
           "-c", "copy", str(out_file)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # reintento recodificando si copy falla
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
               "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(out_file)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and out_file.exists()
    if not ok:
        utils.log.error("Concatenación falló: %s", r.stderr[-300:])
    # Limpieza opcional de clips intermedios
    try:
        shutil.rmtree(work)
    except Exception:
        pass
    return ok


# --------------------------------------------------------------------------
def main() -> int:
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
    utils.log.info("2/3 Preparando imágenes...")
    images = prepare_images(escenas, images_dir)
    utils.log.info("3/3 Ensamblando video con FFmpeg...")

    out_file = video_dir / "final.mp4"
    ok = build_video(escenas, images, audios, out_file)

    if ok:
        utils.log.info("Video listo: %s", out_file)
        if not args.no_telegram and utils.telegram_configured():
            sent = utils.telegram_send_document(out_file, caption=f"Video listo: {tema}")
            if not sent:
                utils.telegram_send(f"Video listo (muy grande para enviar): {out_file}")
        print(f"\n=== VIDEO GENERADO ===\n{out_file}")
        return 0

    utils.log.error("No se pudo generar el video.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
