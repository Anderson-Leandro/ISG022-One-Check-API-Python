# Popula o banco no Render via POST
# Uso: .\scripts\populate_render.ps1
# Requer SEED_SECRET configurado no Render (Environment)

$ApiUrl = "https://onecheck-api.onrender.com/api/v1/admin/seed"
$Secret = $env:SEED_SECRET
if (-not $Secret) {
    Write-Host "Defina a variavel de ambiente SEED_SECRET com o mesmo valor configurado no Render."
    exit 1
}

Write-Host "POST $ApiUrl"

try {
    $response = Invoke-RestMethod -Uri $ApiUrl -Method POST `
        -Headers @{ "X-Seed-Secret" = $Secret; "Content-Type" = "application/json" } `
        -Body '{"force":false}' `
        -TimeoutSec 120

    $response | ConvertTo-Json -Depth 6
} catch {
    Write-Host "Erro: $($_.Exception.Message)"
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    Write-Host ""
    Write-Host "Se retornou 404, faca deploy da versao nova da API com o endpoint /admin/seed"
    Write-Host "Configure SEED_SECRET no Render e use o mesmo valor aqui."
}
