# ============================================================
#  start_all.ps1  -  Inicia TODO el entorno de Content Factory
#  Uso: clic derecho > "Ejecutar con PowerShell"  (o doble clic en start_all.bat)
# ============================================================

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[AVISO] $msg" -ForegroundColor Yellow }

Write-Host "============================================================"
Write-Host " CONTENT FACTORY - Inicio completo del entorno"
Write-Host "============================================================"

# --- 1. Configuracion (.env) ---
Step "Comprobando configuracion (.env)"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Warn "Se creo .env desde .env.example. Edita .env y pon tus claves de Telegram."
} else {
    Ok ".env existe (no se toca)."
}

# --- 2. Entorno Python + dependencias ---
Step "Preparando entorno Python"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Ok "Entorno virtual creado (.venv)."
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
Ok "Dependencias instaladas."

# --- 3. Ollama: servicio + modelo ---
Step "Comprobando Ollama"
$ollamaExe = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaExe) {
    Warn "No encontre 'ollama' en el PATH. Instalalo desde https://ollama.com/download"
} else {
    $ollamaUp = (Test-NetConnection -ComputerName localhost -Port 11434 -WarningAction SilentlyContinue).TcpTestSucceeded
    if (-not $ollamaUp) {
        Warn "Ollama no responde. Iniciandolo en segundo plano (ollama serve)..."
        Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve" -ErrorAction SilentlyContinue
        for ($i=0; $i -lt 10; $i++) {
            Start-Sleep -Seconds 2
            $ollamaUp = (Test-NetConnection -ComputerName localhost -Port 11434 -WarningAction SilentlyContinue).TcpTestSucceeded
            if ($ollamaUp) { break }
        }
    }
    if ($ollamaUp) {
        Ok "Ollama activo en localhost:11434"
        $model = "llama3.1:8b"
        $models = (& ollama list) 2>$null
        if ($models -notmatch "llama3.1") {
            Step "Descargando el modelo $model (~5 GB, solo la primera vez)"
            & ollama pull $model
        }
        Ok "Modelo $model disponible."
    } else {
        Warn "No pude conectar con Ollama. Abre la app de Ollama manualmente y reintenta."
    }
}

# --- 3b. ComfyUI (opcional) ---
Step "Comprobando ComfyUI (opcional)"
$comfyUp = (Test-NetConnection -ComputerName localhost -Port 8188 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($comfyUp) {
    Ok "ComfyUI ya esta activo en localhost:8188"
} else {
    # Si defines COMFYUI_PATH en .env, intento lanzarlo. Si no, solo aviso.
    $comfyPath = (Select-String -Path ".env" -Pattern "^COMFYUI_PATH=(.+)$" -ErrorAction SilentlyContinue).Matches.Groups[1].Value
    if ($comfyPath -and (Test-Path $comfyPath)) {
        Warn "Iniciando ComfyUI desde $comfyPath ..."
        if ($comfyPath -match "\.bat$") {
            Start-Process -FilePath $comfyPath -WorkingDirectory (Split-Path $comfyPath)
        } else {
            Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory $comfyPath
        }
        Warn "ComfyUI tarda en cargar; las imagenes se generaran cuando este listo."
    } else {
        Warn "ComfyUI no activo. Es OPCIONAL: sin el, el video usa placeholders y deja los prompts listos."
        Warn "Para arranque automatico, agrega COMFYUI_PATH a tu .env (ruta a run_nvidia_gpu.bat o a la carpeta de ComfyUI)."
    }
}

# --- 4. Docker + n8n ---
Step "Comprobando Docker / n8n"
$dockerOk = $false
try { docker ps *> $null; if ($LASTEXITCODE -eq 0) { $dockerOk = $true } } catch {}
if (-not $dockerOk) {
    Warn "Docker no esta corriendo. Abriendo Docker Desktop..."
    $dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) {
        Start-Process $dd
        Write-Host "Esperando a que Docker arranque (hasta 90s)..."
        for ($i=0; $i -lt 18; $i++) {
            Start-Sleep -Seconds 5
            docker ps *> $null
            if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
        }
    } else {
        Warn "No encontre Docker Desktop. Instalalo o abrelo manualmente."
    }
}
if ($dockerOk) {
    docker compose up -d
    Ok "n8n levantado en http://localhost:5678"
} else {
    Warn "n8n NO se inicio (Docker no disponible). El resto del flujo funciona igual."
}

# --- 5. Diagnostico final ---
Step "Verificando servicios"
& ".\.venv\Scripts\python.exe" "scripts\check_services.py"

Write-Host "`n============================================================"
Write-Host " LISTO. Para generar contenido ejecuta run_pipeline.bat"
Write-Host " o manualmente:"
Write-Host "   .\.venv\Scripts\python.exe scripts\generate_ideas.py --tema `"tu tema`""
Write-Host "============================================================"
Read-Host "`nPresiona ENTER para cerrar"
