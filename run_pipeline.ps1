# ============================================================
#  run_pipeline.ps1  -  Flujo guiado: ideas -> guion -> video
#  Semiautomatico: tu apruebas la idea antes de seguir.
# ============================================================

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }  # fallback si no hay venv

Write-Host "============================================================"
Write-Host " CONTENT FACTORY - Flujo guiado de creacion"
Write-Host "============================================================"

# --- Tema ---
$tema = Read-Host "Tema del video (ej. finanzas personales)"
if ([string]::IsNullOrWhiteSpace($tema)) { Write-Host "Tema vacio. Saliendo."; exit 1 }

$n = Read-Host "Cuantas ideas generar? (ENTER = 5)"
if ([string]::IsNullOrWhiteSpace($n)) { $n = 5 }

# --- 1. Ideas ---
Write-Host "`n==> Generando ideas..." -ForegroundColor Cyan
& $py "scripts\generate_ideas.py" --tema "$tema" --n $n
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo generando ideas."; Read-Host "ENTER"; exit 1 }

# --- 2. Aprobacion (control humano) ---
Write-Host "`nRevisa las ideas arriba (o en Telegram)." -ForegroundColor Yellow
$idea = Read-Host "Numero de la idea que apruebas (ENTER = 1)"
if ([string]::IsNullOrWhiteSpace($idea)) { $idea = 1 }

# --- 3. Guion ---
Write-Host "`n==> Generando guion de la idea $idea..." -ForegroundColor Cyan
& $py "scripts\generate_script.py" --tema "$tema" --idea $idea
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo generando guion."; Read-Host "ENTER"; exit 1 }

# --- 4. Video ---
$go = Read-Host "`nArmar el video ahora? (S/n)"
if ($go -eq "n" -or $go -eq "N") {
    Write-Host "Listo. Cuando quieras: $py scripts\create_video.py --tema `"$tema`""
} else {
    Write-Host "`n==> Armando video..." -ForegroundColor Cyan
    & $py "scripts\create_video.py" --tema "$tema"
}

Write-Host "`n============================================================"
Write-Host " Flujo completado. Revisa la carpeta outputs\videos\"
Write-Host "============================================================"
Read-Host "Presiona ENTER para cerrar"
