# Flujo de la fábrica de contenido

El proceso es **semiautomático**: hay puntos de control humano (aprobación)
antes de invertir cómputo en guion, audio, imágenes y video.

```
[1] Generar ideas (Ollama)
        │  generate_ideas.py
        ▼
[2] Enviar a Telegram para revisión
        │  (notificación)
        ▼
[3] Aprobar una idea  ◄── CONTROL HUMANO
        │  (eliges el número de idea)
        ▼
[4] Generar guion (Ollama)
        │  generate_script.py
        ▼
[5] Dividir en escenas  ──►  [6] Prompts de imagen por escena
        │                          (guion.json / prompts_imagenes.txt)
        ▼
[7] Audio narrado (edge-tts)
        │  create_video.py
        ▼
[8] Imágenes (ComfyUI o placeholders) ◄── CONTROL HUMANO opcional
        │
        ▼
[9] Ensamblar video (FFmpeg)
        │
        ▼
[10] Guardar ordenado por fecha y tema
        │  outputs/videos/<fecha>_<tema>/final.mp4
        ▼
[11] Enviar resultado/resumen a Telegram
```

## Responsabilidad de cada herramienta

| Herramienta | Rol |
|---|---|
| **n8n** | Orquesta el flujo y los disparadores (webhooks, cron, Telegram). |
| **Python** | Ejecuta las tareas pesadas (los `scripts/`). |
| **Ollama** | Genera ideas, guiones y prompts de imagen (proveedor principal de texto). |
| **Telegram** | Aprobación y notificaciones. |
| **ComfyUI** | Genera imágenes cuando está disponible (si no, placeholders). |
| **FFmpeg / MoviePy** | Arma el video final. |
| **edge-tts** | Voz narrada gratuita y local (ElevenLabs es opcional). |

## Estados de una idea (database/ideas.json)

- `pendiente` — recién generada, esperando revisión.
- `aprobada` — seleccionada para generar guion.
- `rechazada` — descartada.

## Convención de salidas

Todo se guarda como `outputs/<tipo>/<YYYY-MM-DD>_<tema-en-slug>/`:

```
outputs/
├─ ideas/2026-06-16_finanzas-personales/ideas.json
├─ scripts/2026-06-16_finanzas-personales/guion.json, narracion.txt, prompts_imagenes.txt
├─ audio/2026-06-16_finanzas-personales/escena_01.mp3 ...
├─ images/2026-06-16_finanzas-personales/escena_01.png ...
└─ videos/2026-06-16_finanzas-personales/final.mp4
```

## Dónde encaja n8n (orquestación)

n8n no reemplaza a los scripts: los **dispara** y conecta con Telegram.
Patrón recomendado para empezar:

1. Nodo **Cron / Manual** → ejecuta `generate_ideas.py` (vía nodo Execute
   Command si n8n corre con acceso al host, o por webhook a un pequeño wrapper).
2. Nodo **Telegram** → envía las ideas y espera respuesta.
3. Nodo **Switch** → según la idea aprobada, dispara `generate_script.py`.
4. Nodo final → dispara `create_video.py` y notifica el resultado.

> Mientras tanto, todo funciona ejecutando los scripts a mano (ver README).
> Los workflows exportados de n8n se guardan en `workflows/`.
