"""
scripts/generate_ideas.py
-------------------------
Paso 1-2 del flujo: genera ideas de video con Ollama y (opcional) las envía a
Telegram para revisión/aprobación manual.

Uso:
    python scripts/generate_ideas.py --tema "finanzas personales" --n 5
    python scripts/generate_ideas.py --tema "curiosidades de la historia" --no-telegram

Salida:
    outputs/ideas/<fecha>_<tema>/ideas.json
    (también registra cada idea en database/ideas.json con estado "pendiente")
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
import utils  # noqa: E402  (mismo directorio scripts/)


def _extract_json(text: str) -> dict:
    """Intenta extraer un objeto JSON de la respuesta del modelo."""
    text = text.strip()
    # Quita posibles fences ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def generate(tema: str, n: int) -> list[dict]:
    template = utils.read_prompt_template("ideas_prompt.txt")
    if not template:
        raise FileNotFoundError("Falta prompts/ideas_prompt.txt")
    prompt = template.format(tema=tema, n=n)
    utils.log.info("Generando %d ideas sobre '%s' con %s...", n, tema, config.OLLAMA_MODEL)
    raw = utils.ollama_generate(prompt, temperature=0.9)
    try:
        data = _extract_json(raw)
        ideas = data.get("ideas", [])
    except Exception:
        utils.log.error("No se pudo parsear JSON del modelo. Respuesta cruda guardada.")
        ideas = [{"titulo": "(sin parsear)", "descripcion": raw[:500]}]
    return ideas


def register_in_db(ideas: list[dict], tema: str, ideas_file: Path) -> None:
    db_path = config.DATABASE_DIR / "ideas.json"
    db = utils.load_json(db_path, default={"ideas": []}) or {"ideas": []}
    for i, idea in enumerate(ideas, 1):
        db["ideas"].append({
            "id": f"{utils.timestamp()}_{i}",
            "fecha": utils.today_str(),
            "tema": tema,
            "titulo": idea.get("titulo", ""),
            "estado": "pendiente",          # pendiente | aprobada | rechazada
            "archivo": str(ideas_file),
        })
    utils.save_json(db_path, db)


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera ideas de video con Ollama.")
    ap.add_argument("--tema", required=True, help="Tema sobre el que generar ideas.")
    ap.add_argument("--n", type=int, default=5, help="Número de ideas (def. 5).")
    ap.add_argument("--no-telegram", action="store_true", help="No enviar a Telegram.")
    args = ap.parse_args()

    if not utils.ollama_available():
        utils.log.error("Ollama no disponible en %s. Inícialo y haz 'ollama pull %s'.",
                        config.OLLAMA_BASE_URL, config.OLLAMA_MODEL)
        return 1

    ideas = generate(args.tema, args.n)

    out_dir = utils.output_dir("ideas", args.tema)
    ideas_file = out_dir / "ideas.json"
    utils.save_json(ideas_file, {"tema": args.tema, "fecha": utils.today_str(), "ideas": ideas})
    register_in_db(ideas, args.tema, ideas_file)
    utils.log.info("Guardadas %d ideas en %s", len(ideas), ideas_file)

    # --- Notificación / aprobación por Telegram ---
    if not args.no_telegram and utils.telegram_configured():
        lines = [f"*Ideas nuevas* — _{args.tema}_ ({utils.today_str()})", ""]
        for i, idea in enumerate(ideas, 1):
            lines.append(f"*{i}. {idea.get('titulo','(sin título)')}*")
            if idea.get("gancho"):
                lines.append(f"   _Gancho:_ {idea['gancho']}")
            if idea.get("descripcion"):
                lines.append(f"   {idea['descripcion']}")
            lines.append("")
        lines.append("Responde con el número de la idea que apruebas para generar el guion.")
        if utils.telegram_send("\n".join(lines)):
            utils.log.info("Ideas enviadas a Telegram para revisión.")
    elif not args.no_telegram:
        utils.log.warning("Telegram no configurado: revisa las ideas en %s", ideas_file)

    # Resumen en consola
    print("\n=== IDEAS GENERADAS ===")
    for i, idea in enumerate(ideas, 1):
        print(f"{i}. {idea.get('titulo','(sin título)')}")
    print(f"\nArchivo: {ideas_file}")
    print("Aprueba una idea y luego ejecuta generate_script.py con --idea <n> y el mismo --tema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
