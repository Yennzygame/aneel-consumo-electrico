# Datos crudos

Esta carpeta no se versiona: los seis archivos anuales del SAMP de ANEEL pesan
~1,8 GB y GitHub rechaza archivos de más de 100 MB.

## Qué descargar

Del portal de datos abiertos de ANEEL
(<https://dadosabertos.aneel.gov.br/>), conjunto **SAMP — Sistema de
Acompanhamento do Mercado de Energia Elétrica**, descargar los archivos anuales
y guardarlos con estos nombres:

| Archivo | Año | Tamaño aproximado |
|---|---:|---:|
| `samp-2021.csv` | 2021 | 251 MB |
| `samp-2022.csv` | 2022 | 258 MB |
| `samp-2023.csv` | 2023 | 297 MB |
| `samp-2024.csv` | 2024 | 352 MB |
| `samp-2025.csv` | 2025 | 371 MB |
| `samp-2026.csv` | 2026 | 262 MB |

La extracción se hizo con datos disponibles hasta 2026-10-15. El mes 2026-09
queda parcial y el pipeline lo excluye (ventana 2021-01 a 2026-08).

## Formato

CSV con separador `;`, codificación UTF-8 y 18 columnas. La columna
`VlrMercado` mezcla unidades según `DscDetalheMercado` (R$, kWh, kW, %, conteos);
el pipeline usa solo `Energia TUSD (kWh)`.

## Verificación

Después de copiar los seis archivos:

```powershell
python -m src.aneel_pipeline --step all
```

El pipeline valida que estén los años esperados y construye
`data/processed/painel_mensal.csv`.
