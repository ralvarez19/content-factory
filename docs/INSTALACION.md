# Instalación y puesta en marcha

Guía para Windows + PowerShell. Ruta del proyecto: `C:\ProyectosIA\content-factory`.

## 0. Estado detectado en tu equipo

- ✅ Python 3.12.10, pip 25
- ✅ FFmpeg 8.1.1 (full, NVENC/CUDA) en PATH
- ✅ Ollama 0.30.6 activo en `:11434` — **sin modelos todavía**
- ✅ GPU NVIDIA RTX 4060 Ti 16GB
- ⚠️ Docker 29.5.3 instalado pero **el daemon no corre** (abre Docker Desktop)
- ⚠️ ComfyUI no activo (opcional)

## 1. Dependencias de Python

```powershell
cd C:\ProyectosIA\content-factory

# Entorno virtual (recomendado)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Si PowerShell bloquea la activación:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Configuración (.env)

```powershell
copy .env.example .env
notepad .env
```

Rellena al menos:

- `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` (para aprobación/notificación).
- `OLLAMA_MODEL` (por defecto `llama3.1:8b`).

> Nunca compartas tu `.env`. Está en `.gitignore`. Para versionar cambios de
> configuración, edita `.env.example` (sin valores reales).

### Obtener el Telegram Bot Token y Chat ID

1. En Telegram, habla con **@BotFather** → `/newbot` → copia el token.
2. Envía cualquier mensaje a tu nuevo bot.
3. Abre en el navegador:
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y copia el
   `chat.id` que aparece.

## 3. Modelo de Ollama

```powershell
ollama pull llama3.1:8b
ollama list
```

## 4. Docker / n8n

```powershell
# Abre Docker Desktop y espera a que diga "running".
cd C:\ProyectosIA\content-factory
docker compose up -d
# n8n en http://localhost:5678
```

Si `docker compose up` falla con un error de daemon
(`pipe/dockerDesktopLinuxEngine ... no puede encontrar el archivo`), significa
que **Docker Desktop no está iniciado**. Ábrelo y reintenta.

## 5. ComfyUI (opcional)

Instálalo/ejecútalo en Windows (fuera de Docker) y verifica `http://localhost:8188`.
Sin ComfyUI, el video se arma con imágenes placeholder y deja los prompts listos
en `outputs/images/<fecha>_<tema>/prompts.txt`.

## 6. Verificación

```powershell
python scripts\check_services.py
# o el chequeo rápido nativo:
powershell -ExecutionPolicy Bypass -File scripts\check_services.ps1
```

Debe mostrar Ollama y FFmpeg en `[ OK ]`. ComfyUI y n8n pueden quedar en
`[AVISO]` (opcionales).

## 7. Prueba de extremo a extremo

```powershell
python scripts\generate_ideas.py --tema "curiosidades del espacio" --n 3
python scripts\generate_script.py --tema "curiosidades del espacio" --idea 1
python scripts\create_video.py --tema "curiosidades del espacio"
```

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker compose` error de daemon | Docker Desktop apagado | Abrir Docker Desktop |
| `generate_ideas` no responde | Ollama sin modelo | `ollama pull llama3.1:8b` |
| Telegram no envía | falta token/chat_id | completar `.env` |
| Sin audio en el video | edge-tts no instalado o sin internet | `pip install edge-tts` |
| Imágenes son placeholders | ComfyUI no activo | iniciar ComfyUI o reemplazar imágenes a mano |
| n8n no llega al host | URL incorrecta | usar `host.docker.internal`, no `localhost`, dentro del contenedor |
