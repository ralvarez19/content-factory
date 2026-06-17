# Content Factory 🎬 (semiautomática)

Fábrica de contenido **semiautomática** para producir videos cortos verticales
(TikTok / Reels / Shorts) en tu propia PC, **gratis y en local**. Tú mantienes el
control: apruebas cada idea antes de gastar tiempo en guion, voz, imágenes y video.

Ruta del proyecto: `C:\ProyectosIA\content-factory`

---

## TL;DR — arranque en 2 pasos

1. **Doble clic en `start_all.bat`** → instala dependencias, descarga el modelo de
   IA, levanta n8n y verifica que todo esté listo.
2. **Doble clic en `run_pipeline.bat`** → te pregunta un tema, genera ideas,
   esperas a aprobar una, y crea el video. Lo encontrarás en `outputs\videos\`.

> Primera vez: edita `.env` (lo crea `start_all` a partir de `.env.example`) y pon
> tu `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` si quieres aprobación/avisos por
> Telegram. Sin Telegram también funciona (revisas las ideas en consola).

---

## ¿Qué hace? (el flujo)

```
[1] Ideas (Ollama) → [2] Aviso a Telegram → [3] APRUEBAS tú
        → [4] Guion + [5] Escenas + [6] Prompts de imagen (Ollama)
        → [7] Voz (edge-tts) → [8] Imágenes (ComfyUI o placeholders)
        → [9] Video (FFmpeg) → [10] Guardado por fecha/tema → [11] Aviso a Telegram
```

Cada salida se guarda ordenada: `outputs/<tipo>/<fecha>_<tema>/`, por ejemplo
`outputs/videos/2026-06-16_finanzas-personales/final.mp4`.

## ¿Cómo lo hace? (qué herramienta hace qué)

| Paso | Herramienta | Detalle |
|---|---|---|
| Ideas, guion, prompts | **Ollama** (local) | Modelo `llama3.1:8b`. Sin coste ni API externa. |
| Aprobación / avisos | **Telegram Bot** | Te manda las ideas y el resultado. Opcional. |
| Voz narrada | **edge-tts** | Gratis, voz neuronal en español. Requiere internet. |
| Imágenes | **ComfyUI** (opcional) | Si está activo en `:8188`, genera con tu checkpoint. Si no, crea *placeholders* y deja los prompts listos. |
| Video | **FFmpeg** | Ensambla imágenes + voz en vertical 1080×1920. |
| Orquestación | **n8n** (Docker) | Conecta los pasos y Telegram. Opcional para empezar. |
| Tareas pesadas | **Python** | Los scripts de `scripts/`. |

---

## ¿Qué necesito? (requisitos)

Detectado ya en tu equipo:

| Herramienta | Estado | Para qué |
|---|---|---|
| Python 3.12 | ✅ instalado | ejecutar los scripts |
| FFmpeg (full) | ✅ instalado | armar el video |
| Ollama | ✅ activo | generar texto (falta `ollama pull`) |
| GPU RTX 4060 Ti 16GB | ✅ | acelera Ollama y ComfyUI |
| Docker Desktop | ⚠️ instalar/abrir | correr n8n |
| ComfyUI | ⚠️ opcional | imágenes con IA |
| Cuenta + bot de Telegram | ⚠️ opcional | aprobación y avisos |

---

## Instalación

### Opción A — automática (recomendada)

Doble clic en **`start_all.bat`**. Hace todo: crea `.venv`, instala
`requirements.txt`, copia `.env.example`→`.env`, descarga `llama3.1:8b`, abre
Docker Desktop, levanta n8n y corre el diagnóstico.

### Opción B — manual (PowerShell)

```powershell
cd C:\ProyectosIA\content-factory
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env                 # pon tus datos de Telegram
ollama pull llama3.1:8b
docker compose up -d         # requiere Docker Desktop abierto
python scripts\check_services.py
```

> **Tu `.env` nunca se sube a git** (está en `.gitignore`). Para compartir
> cambios de configuración usa `.env.example` (sin valores reales).

### Obtener el bot de Telegram

1. En Telegram, habla con **@BotFather** → `/newbot` → copia el **token**.
2. Envía cualquier mensaje a tu nuevo bot.
3. Abre `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y copia el `chat.id`.
4. Pégalos en `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

---

## Uso

### Flujo guiado (lo más fácil)

Doble clic en **`run_pipeline.bat`** (o `.\.venv\Scripts\python.exe` + scripts).
Te pregunta el tema, genera ideas, esperas para aprobar una, y arma el video.

### Comando por comando

```powershell
cd C:\ProyectosIA\content-factory

# 1) Verificar servicios
python scripts\check_services.py

# 2) Generar ideas (van a Telegram si está configurado)
python scripts\generate_ideas.py --tema "finanzas personales" --n 5

# 3) Generar el guion de la idea aprobada (p.ej. la 1)
python scripts\generate_script.py --tema "finanzas personales" --idea 1

# 4) Armar el video final
python scripts\create_video.py --tema "finanzas personales"
```

Resultado en `outputs\videos\<fecha>_<tema>\final.mp4`.

---

## Cómo probar cada servicio

```powershell
# Ollama
ollama list
ollama run llama3.1:8b "Hola"

# n8n  -> abre http://localhost:5678
docker compose up -d

# ComfyUI (opcional) -> abre http://localhost:8188
# Diagnóstico de todo:
python scripts\check_services.py
```

## ComfyUI (imágenes con IA)

Inícialo en Windows (fuera de Docker). Ajusta en `.env`:

```
COMFYUI_CKPT=tu_checkpoint.safetensors   # nombre EXACTO del modelo instalado
```

`create_video.py` usará `config/comfyui_workflow.json` (txt2img) para generar una
imagen por escena. Si ComfyUI no está activo, crea *placeholders* y guarda los
prompts en `outputs/images/<fecha>_<tema>/prompts.txt` para que los generes a mano.

## n8n (orquestación)

Importa el workflow de ejemplo `workflows/ideas_to_telegram.json`
(menú **⋮ → Import from File**). Dentro del contenedor, n8n llama a los servicios
del host con:

- Ollama → `http://host.docker.internal:11434`
- ComfyUI → `http://host.docker.internal:8188`

---

## Estructura del proyecto

```
content-factory/
├─ start_all.bat / .ps1      ← inicia TODO el entorno
├─ run_pipeline.bat / .ps1   ← flujo guiado ideas→guion→video
├─ config/
│  ├─ config.py              carga .env (sin exponer claves)
│  └─ comfyui_workflow.json  plantilla txt2img para ComfyUI
├─ scripts/
│  ├─ utils.py               helpers: rutas por fecha/tema, Ollama, Telegram, logs
│  ├─ check_services.py/.ps1 diagnóstico
│  ├─ generate_ideas.py      paso 1-2
│  ├─ generate_script.py     paso 4-6
│  └─ create_video.py        paso 7-11
├─ prompts/                  plantillas de prompts (ideas, guion)
├─ workflows/                workflows de n8n (.json)
├─ outputs/                  TODO lo generado: ideas/ scripts/ audio/ images/ videos/
├─ database/ideas.json       registro y estado de ideas
├─ logs/                     content-factory.log
├─ docs/                     FLUJO.md, INSTALACION.md
├─ docker-compose.yml        n8n
├─ .env.example              plantilla de configuración (sin secretos)
└─ requirements.txt
```

---

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `docker compose` error de daemon | Docker Desktop apagado | Ábrelo y reintenta (o usa `start_all.bat`) |
| Las ideas no se generan | Ollama sin modelo | `ollama pull llama3.1:8b` |
| El video sale sin voz | sin internet o edge-tts no instalado | revisa conexión / `pip install edge-tts` |
| Las imágenes son placeholders | ComfyUI no activo | inícialo o reemplaza las imágenes a mano |
| Telegram no envía | falta token/chat_id | completa `.env` |
| n8n no alcanza Ollama | usó `localhost` | dentro del contenedor usa `host.docker.internal` |
| PowerShell bloquea el script | ExecutionPolicy | los `.bat` ya usan `-ExecutionPolicy Bypass` |

---

## Próximos pasos sugeridos

- Orquestación completa en n8n con **botones de aprobar/rechazar** en Telegram.
- Subtítulos quemados con FFmpeg a partir de `narracion.txt`.
- Música de fondo y transiciones entre escenas.
- Voz premium opcional con ElevenLabs (`.env`).
- Cola de revisión antes de publicar.

Documentación ampliada: [`docs/FLUJO.md`](docs/FLUJO.md) y
[`docs/INSTALACION.md`](docs/INSTALACION.md).
