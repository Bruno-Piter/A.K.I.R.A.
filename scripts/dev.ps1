#Requires -Version 5.1
Set-Location $PSScriptRoot\..
docker compose up -d neo4j
Write-Host "Neo4j: http://localhost:7474  bolt://localhost:7687"
Write-Host "Backend: cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
Write-Host "Frontend: cd frontend; npm run dev"
