"""
scripts/generate_script.py
--------------------------
Pasos 4-6 del flujo: a partir de una idea aprobada, genera el guion completo,
dividido en escenas, con narración y prompts de imagen por escena.

Uso (elige la idea por número del archivo ideas.json del mismo tema/fecha):
    python scripts/generate_script.py --tema "finanzas personales" --idea 1

O apuntando directamente a un archivo de ideas:
    python scripts/generate_script.py --ideas-file "outputs/ideas/2026-06-16_finanzas/ideas.json" --idea 2

Salida:
    outputs/scripts/<fecha>_<tema>/guion.json
    outputs/scripts/<fecha>_<tema>/narracion.txt
    outputs/scripts/<fecha>_<tema>/prompts_imagenes.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import config  # noqa: E402
import utils  # noqa: E402


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def find_ideas_file(tema: str | None, ideas_file: str | None) -> Path:
    if ideas_file:
        p = Path(ideas_file)
        if not p.is_absolute():
            p = config.ROOT_DIR / p
        return p
    # Buscar el ideas.json más reciente del tema
    folder = config.IDEAS_DIR / f"{utils.today_str()}_{utils.slugify(tema)}"
    p = folder / "ideas.json"
    if p.exists():
        return p
    # fallback: cualquier carpeta que contenga el slug del tema
    matches = sorted(config.IDEAS_DIR.glob(f"*_{utils.slugify(tema)}/ideas.json"))
    if matches:
        return matches[-1]
    raise FileNotFoundError(f"No encuentro ideas.json para el tema '{tema}'. Genera ideas primero.")


def generate_script(idea: dict) -> dict:
    template = utils.read_prompt_template("script_prompt.txt")
    if not template:
        raise FileNotFoundError("Falta prompts/script_prompt.txt")
    prompt = template.format(
        titulo=idea.get("titulo", ""),
        gancho=idea.get("gancho", ""),
        descripcion=idea.get("descripcion", ""),
        publico=idea.get("publico", "general"),
        formato=idea.get("formato", "narrado"),
    )
    utils.log.info("Generando guion para: %s", idea.get("titulo", ""))
    raw = utils.ollama_generate(prompt, temperature=0.7)
    return _extract_json(raw)


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera el guion de una idea aprobada.")
    ap.add_argument("--tema", help="Tema usado al generar las ideas.")
    ap.add_argument("--ideas-file", help="Ruta directa a un ideas.json.")
    ap.add_argument("--idea", type=int, default=1, help="Número de idea a usar (def. 1).")
    args = ap.parse_args()

    if not args.tema and not args.ideas_file:
        ap.error("Indica --tema o --ideas-file.")

    if not utils.ollama_available():
        utils.log.error("Ollama no disponible en %s.", config.OLLAMA_BASE_URL)
        return 1

    ideas_path = find_ideas_file(args.tema, args.ideas_file)
    data = utils.load_json(ideas_path)
    ideas = data.get("ideas", [])
    tema = data.get("tema", args.tema or "tema")
    if not (1 <= args.idea <= len(ideas)):
        utils.log.error("Idea %d fuera de rango (hay %d).", args.idea, len(ideas))
        return 1
    idea = ideas[args.idea - 1]

    guion = generate_script(idea)
    escenas = guion.get("escenas", [])

    out_dir = utils.output_dir("scripts", tema)
    utils.save_json(out_dir / "guion.json", guion)

    # Archivos auxiliares para audio e imágenes
    narracion = "\n\n".join(e.get("narracion", "") for e in escenas)
    (out_dir / "narracion.txt").write_text(narracion, encoding="utf-8")

    prompts_txt = "\n".join(
        f"Escena {e.get('numero', i+1)}: {e.get('prompt_imagen','')}"
        for i, e in enumerate(escenas)
    )
    (out_dir / "prompts_imagenes.txt").write_text(prompts_txt, encoding="utf-8")

    utils.log.info("Guion con %d escenas guardado en %s", len(escenas), out_dir)

    if utils.telegram_configured():
        utils.telegram_send(
            f"*Guion listo* — {guion.get('titulo', idea.get('titulo',''))}\n"
            f"{len(escenas)} escenas. Revisa antes de generar el video."
        )

    print("\n=== GUION GENERADO ===")
    print(f"Título: {guion.get('titulo', idea.get('titulo',''))}")
    print(f"Escenas: {len(escenas)}")
    print(f"Carpeta: {out_dir}")
    print("Siguiente paso: python scripts/create_video.py --tema \"%s\"" % tema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
