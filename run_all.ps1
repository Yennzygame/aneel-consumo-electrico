<#
.SYNOPSIS
    Reproduce el pipeline completo del proyecto ANEEL / IND2622.

.DESCRIPTION
    Ejecuta, en orden:
      1. Panel unidad x mes, matrices y features        (~1 min)
      2. Diseno de experimentos de 504 corridas + MLflow (~3-4 min)
      3. Modelo final, arquetipos, tests y 13 figuras    (~1 min)
      4. Contexto de mercado cativo / libre / GD         (~1,5 min)

    Los pasos son idempotentes: reutilizan artefactos existentes.
    Con -Force se recalculan todos.

.PARAMETER Force
    Fuerza el recalculo de todos los artefactos.

.PARAMETER Quick
    Ejecuta un DoE reducido (util para probar el entorno). No sobrescribe
    los resultados completos salvo que se combine con -Force.

.PARAMETER WithNotebooks
    Ejecuta ademas los 5 notebooks de punta a punta (~10-15 min).

.EXAMPLE
    .\run_all.ps1

.EXAMPLE
    .\run_all.ps1 -Force -WithNotebooks
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Quick,
    [switch]$WithNotebooks
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Invoke-Paso {
    param(
        [string]$Nombre,
        [string[]]$Argumentos
    )

    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Cyan
    Write-Host "  $Nombre" -ForegroundColor Cyan
    Write-Host "==============================================================" -ForegroundColor Cyan

    $inicio = Get-Date
    & python @Argumentos
    if ($LASTEXITCODE -ne 0) {
        throw "El paso '$Nombre' fallo con codigo $LASTEXITCODE."
    }
    $min = ((Get-Date) - $inicio).TotalMinutes
    Write-Host ("  OK - {0:N1} min" -f $min) -ForegroundColor Green
}

Write-Host "Proyecto: $root"
Write-Host ("Python:   " + (& python --version 2>&1))

if (-not (Test-Path "data\raw")) {
    throw "No existe data\raw. Copiar alli los 6 CSV anuales del SAMP de ANEEL."
}

$csv = @(Get-ChildItem "data\raw\*.csv" -ErrorAction SilentlyContinue)
if ($csv.Count -eq 0) {
    throw "data\raw no contiene CSV. Descargar los archivos samp-<anio>.csv de ANEEL/SAMP."
}
Write-Host ("CSV crudos detectados: " + $csv.Count)

$panelArgs = @("-m", "src.aneel_pipeline", "--step", "all")
if ($Force) { $panelArgs += "--force" }

$doeArgs = @("-m", "src.doe")
if ($Quick) { $doeArgs += "--quick" } else { $doeArgs += "--full" }
if ($Force) { $doeArgs += "--force" }

$secuencia = @(
    @{ Nombre = "1/4 - Panel, matrices y features";      Args = $panelArgs },
    @{ Nombre = "2/4 - Diseno de experimentos (DoE)";    Args = $doeArgs },
    @{ Nombre = "3/4 - Modelo final y figuras";          Args = @("-m", "src.select_final", "--auto") },
    @{ Nombre = "4/4 - Contexto de mercado";             Args = @("-m", "src.analisis_mercado") }
)

$t0 = Get-Date
foreach ($p in $secuencia) {
    Invoke-Paso -Nombre $p.Nombre -Argumentos $p.Args
}

if ($WithNotebooks) {
    $notebooks = Get-ChildItem "notebooks\*.ipynb" | Sort-Object Name
    foreach ($nb in $notebooks) {
        Invoke-Paso -Nombre ("Notebook: " + $nb.Name) -Argumentos @(
            "-m", "nbconvert",
            "--to", "notebook",
            "--execute", "--inplace",
            "--ExecutePreprocessor.timeout=900",
            $nb.FullName
        )
    }

    $htmlArgs = @("-m", "nbconvert", "--to", "html", "--output-dir", "reports\html")
    $htmlArgs += $notebooks.FullName
    Invoke-Paso -Nombre "Export HTML de notebooks" -Argumentos $htmlArgs
}

$total = ((Get-Date) - $t0).TotalMinutes
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ("  Pipeline completo - {0:N1} min" -f $total) -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Artefactos principales:"
Write-Host "  reports\tables\final_resumen.json"
Write-Host "  reports\tables\doe_resultados.csv"
Write-Host "  reports\figures\*.png"
Write-Host "  mlflow.db"
Write-Host ""
Write-Host "Para ver MLflow:"
Write-Host "  mlflow ui --backend-store-uri sqlite:///mlflow.db"
