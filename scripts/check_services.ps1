# ============================================================
#  check_services.ps1
#  Verificación rápida de servicios para Content Factory (Windows).
#  Uso:  powershell -ExecutionPolicy Bypass -File scripts\check_services.ps1
# ============================================================

$ErrorActionPreference = "SilentlyContinue"

Write-Host "============================================================"
Write-Host " CONTENT FACTORY - Verificacion de servicios (PowerShell)"
Write-Host "============================================================"

function Test-Port($name, $port) {
    $conn = Test-NetConnection -ComputerName "localhost" -Port $port -WarningAction SilentlyContinue
    if ($conn.TcpTestSucceeded) {
        Write-Host "[ OK ] $name activo en puerto $port"
        return $true
    } else {
        Write-Host "[AVISO] $name NO responde en puerto $port"
        return $false
    }
}

# --- Ollama (requerido) ---
$ollama = Test-Port "Ollama" 11434
if ($ollama) {
    $models = (& ollama list) 2>$null
    if ($models -and $models.Count -gt 1) {
        Write-Host "       Modelos instalados:"
        $models | Select-Object -Skip 1 | ForEach-Object { Write-Host "         $_" }
    } else {
        Write-Host "[AVISO] Ollama sin modelos. Ejecuta: ollama pull llama3.1:8b"
    }
}

# --- ComfyUI (opcional) ---
Test-Port "ComfyUI" 8188 | Out-Null

# --- n8n (opcional) ---
$n8n = Test-Port "n8n" 5678
if (-not $n8n) {
    Write-Host "       Para iniciar n8n: docker compose up -d  (requiere Docker Desktop activo)"
}

# --- FFmpeg (requerido) ---
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    $ver = (& ffmpeg -version | Select-Object -First 1)
    Write-Host "[ OK ] $ver"
} else {
    Write-Host "[FALLA] FFmpeg no esta en el PATH."
}

# --- Docker ---
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $info = (& docker ps 2>&1)
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[ OK ] Docker daemon activo."
    } else {
        Write-Host "[AVISO] Docker instalado pero el daemon NO corre. Abre Docker Desktop."
    }
} else {
    Write-Host "[AVISO] Docker no encontrado."
}

Write-Host "============================================================"
Write-Host " Sugerencia: para un chequeo completo ejecuta tambien:"
Write-Host "   python scripts\check_services.py"
Write-Host "============================================================"
