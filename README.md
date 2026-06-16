# Content Factory (semiautomática)

Fábrica de contenido **semiautomática** para generar videos cortos verticales
(TikTok / Reels / Shorts). El flujo está pensado para tener **control manual**
en cada paso clave: tú apruebas las ideas antes de gastar tiempo en guion,
audio, imágenes y video.

Prioridad: **funcionar 100% local y gratis** primero (Ollama + FFmpeg + edge-tts).
Las APIs de pago (ElevenLabs, OpenAI, etc.) son opcionales.

Ruta del proyecto: `C:\ProyectosIA\content-factory`

---

## Requisitos

Ya verificados en tu equipo (✅) o por activar (⚠️):

| Herramienta | Estado | Notas |
|---|---|---|
| Python 3.12 | ✅ | `python --version` |
| FFmpeg (full) | ✅ | en PATH, con NVENC/CUDA |
| Ollama | ✅ activo | falta descargar un modelo |
| Docker Desktop | ⚠️ instalado, apagado | necesario para n8n |
| ComfyUI | ⚠️ opcional | imágenes; si no está, se usan placeholders |
| GPU NVIDIA RTX 4060 Ti 16GB | ✅ | sobra para modelos 8B y ComfyUI |

---

## Instalación

Ver guía detallada en [`docs/INSTALACION.md`](docs/INSTALACION.md). Resumen:

```powershell
cd C:\ProyectosIA\content-factory

# 1. Dependencias Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configuración: copia el ejemplo y rellena tus claves
copy .env.example .env
notepad .env     # pon TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, etc.

# 3. Modelo de texto en Ollama
ollama pull llama3.1:8b
```

> Tu `.env` real **nunca** se sube a git (está protegido por `.gitignore`).

---

## Estructura

```
content-factory/
├─ config/            # config.py: carga .env (sin exponer claves)
├─ scripts/           # scripts de Python (el motor)
│  ├─ utils.py            # helpers: rutas por fecha/tema, Ollama, Telegram, logging
│  ├─ check_services.py   # diagnóstico de servicios
│  ├─ check_services.ps1  # versión PowerShell
│  ├─ generate_ideas.py   # paso 1-2: ideas -> Telegram
│  ├─ generate_script.py  # paso 4-6: guion + escenas + prompts de imagen
│  └─ create_video.py     # paso 7-11: audio + imágenes + video final
├─ prompts/           # plantillas de prompts (ideas, guion)
├─ workflows/         # workflows de n8n (export/import .json)
├─ outputs/           # TODO el contenido generado, ordenado por fecha y tema
│  ├─ ideas/  scripts/  audio/  images/  videos/
├─ database/          # ideas.json: registro y estado de ideas
├─ logs/              # content-factory.log
├─ docs/              # FLUJO.md, INSTALACION.md
├─ docker-compose.yml # n8n
├─ .env.example       # plantilla de configuración (sin secretos)
└─ requirements.txt
```

Cada salida se guarda como `outputs/<tipo>/<fecha>_<tema>/`, por ejemplo
`outputs/videos/2026-06-16_finanzas-personales/final.mp4`.

---

## Cómo correr n8n

```powershell
# Asegúrate de que Docker Desktop esté abierto y corriendo.
cd C:\ProyectosIA\content-factory
docker compose up -d
# Abre http://localhost:5678
```

Desde n8n, para llamar a servicios del host (nodos HTTP Request):

- Ollama → `http://host.docker.internal:11434`
- ComfyUI → `http://host.docker.internal:8188`

Apagar: `docker compose down`.

---

## Cómo probar Ollama

```powershell
ollama list                       # ver modelos instalados
ollama run llama3.1:8b "Hola"     # prueba rápida
# o vía API:
curl http://localhost:11434/api/tags
```

## Cómo probar ComfyUI (opcional)

Inícialo en Windows (fuera de Docker) y abre `http://localhost:8188`.
Si no está activo, `create_video.py` genera **placeholders** con los prompts
listos para que generes las imágenes a mano.

---

## Cómo generar una idea

```powershell
python scripts\check_services.py
python scripts\generate_ideas.py --tema "finanzas personales" --n 5
```

Las ideas se guardan en `outputs/ideas/<fecha>_<tema>/ideas.json`, se registran
en `database/ideas.json` y (si configuraste Telegram) se envían al chat para que
**apruebes** una.

## Cómo generar un guion

```powershell
# usa el número de la idea aprobada
python scripts\generate_script.py --tema "finanzas personales" --idea 1
```

Genera `guion.json` (escenas con narración + prompt de imagen), más
`narracion.txt` y `prompts_imagenes.txt`.

## Cómo armar un video

```powershell
python scripts\create_video.py --tema "finanzas personales"
```

Crea el audio (edge-tts), prepara las imágenes (ComfyUI o placeholders) y
ensambla `outputs/videos/<fecha>_<tema>/final.mp4`. Si Telegram está
configurado, lo envía o avisa.

---

## Flujo completo (comandos)

```powershell
cd C:\ProyectosIA\content-factory
docker compose up -d
python scripts\check_services.py
python scripts\generate_ideas.py --tema "tu tema"
# (apruebas una idea)
python scripts\generate_script.py --tema "tu tema" --idea 1
python scripts\create_video.py --tema "tu tema"
```

Diagrama y detalle en [`docs/FLUJO.md`](docs/FLUJO.md).

---

## Próximos pasos

- Integrar el envío real de workflows a ComfyUI (`config/comfyui_workflow.json`).
- Botones de aprobar/rechazar en Telegram (callback) orquestados por n8n.
- Subtítulos quemados con FFmpeg a partir de `narracion.txt`.
- Música de fondo y transiciones entre escenas.
- Publicación semiautomática (cola de revisión antes de subir).
