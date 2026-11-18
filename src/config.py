"""Configuracion central del proyecto ANEEL / IND2622.

Todas las rutas son relativas a la raiz del proyecto para que el pipeline sea
reproducible en otra maquina.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
TABLES_DIR = REPORTS_DIR / "tables"
ORANGE_DIR = REPORTS_DIR / "orange"
MODELS_DIR = ROOT / "models"
DOCS_DIR = ROOT / "docs"

for _d in (PROCESSED_DIR, FIGURES_DIR, TABLES_DIR, ORANGE_DIR, MODELS_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Ventana temporal
# ---------------------------------------------------------------------------
# 2026-09 se excluye: el corte de generacion (2026-10-15) deja ese mes parcial
# (2,4 TWh frente a ~20 TWh de un mes completo).
MES_INICIO = "2021-01"
MES_FIN = "2026-08"
MESES = pd.period_range(MES_INICIO, MES_FIN, freq="M")
MESES_STR = [str(m) for m in MESES]
N_MESES = len(MESES_STR)

# ---------------------------------------------------------------------------
# Filtros de negocio
# ---------------------------------------------------------------------------
TIPO_MERCADO = "Regular"          # excluye refacturacion, GD, aislado, RTE
OPCION_ENERGIA = "CATIVO"         # mercado cativo regulado
DETALLE_ENERGIA = "Energia TUSD (kWh)"   # TE es identica; nunca sumar ambas
DETALLE_CONSUMIDORES = "Número de consumidores"

# Clases que representan segmentos de mercado. Se excluyen "No se aplica"
# (agregados administrativos) y "Consumo propio" (no es mercado atendido).
CLASES = [
    "Residencial",
    "Comercial",
    "Industrial",
    "Rural",
    "Poder público",
    "Iluminação pública",
    "Serviço público",
]
MAPA_CLASES = {"Serviço Público": "Serviço público"}

# ---------------------------------------------------------------------------
# Reproducibilidad
# ---------------------------------------------------------------------------
RANDOM_STATE = 42
K_RANGE = list(range(2, 9))

# ---------------------------------------------------------------------------
# MLflow
# ---------------------------------------------------------------------------
MLFLOW_DB = ROOT / "mlflow.db"
MLARTIFACTS_DIR = ROOT / "mlartifacts"
EXPERIMENTO_DOE = "ANEEL_Clustering_DoE"
EXPERIMENTO_FINAL = "ANEEL_Clustering_Final"
