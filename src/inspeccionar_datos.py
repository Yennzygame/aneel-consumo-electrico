from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as C

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

meta = pd.read_csv(C.PROCESSED_DIR / "unidades_meta.csv", index_col=0)
serie = pd.read_csv(C.PROCESSED_DIR / "matriz_serie68_mwh.csv", index_col=0)
est = pd.read_csv(C.PROCESSED_DIR / "matriz_estacional12_mwh.csv", index_col=0)
desc = pd.read_csv(C.PROCESSED_DIR / "descriptores.csv", index_col=0)
pca = pd.read_csv(C.PROCESSED_DIR / "pca_serie68.csv", index_col=0)
var = pd.read_csv(C.PROCESSED_DIR / "pca_varianza.csv")

print("=== COBERTURA ===")
print(meta["cobertura"].describe())
print("unidades por cobertura:")
print(meta["cobertura"].round(2).value_counts().sort_index().tail(15))
print("\nExcluidas por motivo:")
print(meta.loc[~meta["incluida"], "motivo_exclusion"].value_counts())

print("\n=== CLASES (incluidas) ===")
print(meta[meta["incluida"]].groupby("clase").agg(
    unidades=("agente", "size"),
    agentes=("agente", "nunique"),
    mwh=("total_mwh", "sum"),
    mediana_mwh=("total_mwh", "median"),
).assign(mwh=lambda d: d["mwh"] / 1e3).sort_values("mwh", ascending=False))

print("\n=== TAMANO POR UNIDAD (MWh totales 68 meses) ===")
print(meta.loc[meta["incluida"], "total_mwh"].describe(
    percentiles=[0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
))
print("unidades < 1 GWh total:", int((meta.loc[meta["incluida"], "total_mwh"] < 1000).sum()))
print("unidades < 10 GWh total:", int((meta.loc[meta["incluida"], "total_mwh"] < 10000).sum()))
print("unidades sin consumidores:", int(meta.loc[meta["incluida"], "consumidores_medios"].isna().sum()))

print("\n=== PCA ===")
print(var.to_string(index=False))

print("\n=== DESCRIPTORES: resumen ===")
cols = [c for c in desc.columns if c not in ("agente", "clase")]
print(desc[cols].describe().T[["mean", "std", "min", "50%", "max"]])
print("\nNaNs en descriptores:", int(desc[cols].isna().sum().sum()))
print("Infinitos:", int(np.isinf(desc[cols].to_numpy(dtype=float)).sum()))

print("\n=== MATRIZ serie68: meses y NaNs ===")
print("shape", serie.shape, "| NaNs", int(serie.isna().sum().sum()),
      "| min", float(serie.min().min()), "| max", float(serie.max().max()))
print("primeras columnas", list(serie.columns[:5]), "...", list(serie.columns[-3:]))

print("\n=== TOP 15 unidades por consumo ===")
print(meta.loc[meta["incluida"]].sort_values("total_mwh", ascending=False)
      .head(15)[["agente", "clase", "total_mwh", "cobertura", "consumidores_medios"]]
      .assign(total_mwh=lambda d: (d["total_mwh"] / 1e3).round(1))
      .to_string())

print("\n=== Distribuidoras y clases ===")
print("agentes:", meta.loc[meta["incluida"], "agente"].nunique())
print(meta.loc[meta["incluida"]].groupby("agente").size().describe())
print("\nClases por agente:")
print(meta.loc[meta["incluida"]].groupby("agente")["clase"].nunique().value_counts().sort_index())
