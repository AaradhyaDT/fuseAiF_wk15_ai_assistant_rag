# ==============================================================================
# WK15 AI Assistant - One-Click Startup Script
# Starts FastAPI Backend on port 8000 and Streamlit UI on port 8501
# ==============================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " [*] Starting WK15 AI Assistant Stack" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# 0. Terminate any existing running instances
Write-Host "[*] Checking for and closing existing instances..." -ForegroundColor Yellow

# Kill by ports (8000 and 8501)
$TargetPorts = @(8000, 8501)
foreach ($Port in $TargetPorts) {
    try {
        $Conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($Conns) {
            $Pids = $Conns | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($P in $Pids) {
                if ($P -gt 0 -and $P -ne $PID) {
                    Write-Host "    - Stopping process on port $Port (PID: $P)..." -ForegroundColor Yellow
                    Stop-Process -Id $P -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        # ignore port query errors
    }
}

# Kill by command line signature (uvicorn / streamlit for this project)
try {
    $Lingering = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        ($_.CommandLine -like "*uvicorn app.main:create_app*" -or $_.CommandLine -like "*streamlit run ui/app.py*") -and $_.ProcessId -ne $PID
    }
    if ($Lingering) {
        foreach ($Proc in $Lingering) {
            Write-Host "    - Stopping matching process '$($Proc.Name)' (PID: $($Proc.ProcessId))..." -ForegroundColor Yellow
            Stop-Process -Id $Proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    # ignore process query errors
}

Start-Sleep -Seconds 1

# 1. Check/activate Virtual Environment
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[!] Virtual environment not found at .venv. Using system python..." -ForegroundColor Yellow
    $PythonExe = "python"
}

# 2. Check for .env file
$EnvFile = Join-Path $ScriptDir ".env"
$EnvExample = Join-Path $ScriptDir ".env.example"
if ((-not (Test-Path $EnvFile)) -and (Test-Path $EnvExample)) {
    Write-Host "[*] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item $EnvExample $EnvFile
}

# 3. Start Backend API Server
Write-Host "`n[*] Starting Backend API (FastAPI) on http://localhost:8000..." -ForegroundColor Green
$BackendProcess = Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn app.main:create_app --factory --port 8000 --host 127.0.0.1" -WorkingDirectory $ScriptDir -PassThru

# Wait briefly for backend to initialize
Start-Sleep -Seconds 3

# 4. Start Streamlit Frontend
Write-Host "[*] Starting Web UI (Streamlit) on http://localhost:8501..." -ForegroundColor Green
$FrontendProcess = Start-Process -FilePath $PythonExe -ArgumentList "-m streamlit run ui/app.py --server.port 8501 --server.address 127.0.0.1" -WorkingDirectory $ScriptDir -PassThru

Write-Host "`n=====================================================" -ForegroundColor Green
Write-Host " [+] Assistant is running!" -ForegroundColor Green
Write-Host " [>] Web UI:      http://localhost:8501" -ForegroundColor Cyan
Write-Host " [>] API Docs:    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "`nPress Ctrl+C or close this window to stop both servers.`n" -ForegroundColor Gray

# Automatically open browser to the UI
Start-Process "http://localhost:8501"

try {
    # Keep the script running to monitor processes and handle graceful shutdown
    while ($BackendProcess -and (-not $BackendProcess.HasExited) -and $FrontendProcess -and (-not $FrontendProcess.HasExited)) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`n[*] Shutting down servers..." -ForegroundColor Yellow
    if ($BackendProcess -and (-not $BackendProcess.HasExited)) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($FrontendProcess -and (-not $FrontendProcess.HasExited)) {
        Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[*] All servers stopped." -ForegroundColor Green
}
