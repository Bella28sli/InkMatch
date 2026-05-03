#!/usr/bin/env pwsh
# Start InkMatchAPI server

Set-Location $PSScriptRoot
.\.venv\Scripts\activate
Write-Host "Starting API on http://localhost:8000" -ForegroundColor Green
Write-Host "Swagger UI: http://localhost:8000/docs" -ForegroundColor Cyan
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
