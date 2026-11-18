"""Diagnostico 2: semantica de VlrMercado y validacion de la variable de consumo.

Objetivo: decidir que filas representan energia consumida (kWh) y comprobar
ordenes de magnitud contra el consumo brasileño (~40-50 TWh/mes total).
"""
from __future__ import annotations

import glob
import os
from collections import Counter, defaultdict

import pandas as pd

RAW_DIR = r"C:\Users\yennz\OneDrive\Documentos\Ciencia de Datos\data\raw"
USE = [
    "DatCompetencia", "VlrMercado", "NomTipoMercado", "DscDetalheMercado",
    "DscOpcaoEnergia", "DscClasseConsumoMercado", "SigAgenteDistribuidora",
    "DscPostoTarifario", "DscSubGrupoTarifario", "DscModalidadeTarifaria",
]

stats = defaultdict(lambda: {"n": 0, "sum": 0.0, "min": None, "max": None, "neg": 0, "zero": 0})
month_tot = defaultdict(float)          # (detalle, mes) -> suma
class_tot = defaultdict(lambda: defaultdict(float))  # (clase, detalle) -> mes -> suma
unit_month = defaultdict(set)           # detalle -> set de (agente, clase, mes)
combo_full = Counter()
n_rows = 0


def parse_br(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma, s.str.replace(".", "", regex=False))
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


for path in sorted(glob.glob(os.path.join(RAW_DIR, "samp-*.csv"))):
    for chunk in pd.read_csv(path, sep=";", encoding="latin1", usecols=USE,
                             chunksize=400_000, dtype=str, low_memory=False):
        n_rows += len(chunk)
        chunk["val"] = parse_br(chunk["VlrMercado"])
        reg = chunk[(chunk["NomTipoMercado"] == "Regular") &
                    (chunk["DscOpcaoEnergia"] == "CATIVO")].copy()
        for det, g in reg.groupby("DscDetalheMercado"):
            v = g["val"]
            st = stats[det]
            st["n"] += len(v)
            st["sum"] += float(v.sum())
            mn, mx = float(v.min()), float(v.max())
            st["min"] = mn if st["min"] is None else min(st["min"], mn)
            st["max"] = mx if st["max"] is None else max(st["max"], mx)
            st["neg"] += int((v < 0).sum())
            st["zero"] += int((v == 0).sum())
        for (det, mes), g in reg.groupby(["DscDetalheMercado", "DatCompetencia"]):
            month_tot[(det, mes)] += float(g["val"].sum())
        for (clase, det, mes), g in reg.groupby(
                ["DscClasseConsumoMercado", "DscDetalheMercado", "DatCompetencia"]):
            class_tot[(clase, det)][mes] += float(g["val"].sum())
        combo_full.update(zip(reg["DscDetalheMercado"], reg["DscClasseConsumoMercado"]))
        for det, g in reg.groupby("DscDetalheMercado"):
            unit_month[det].update(
                zip(g["SigAgenteDistribuidora"], g["DscClasseConsumoMercado"], g["DatCompetencia"])
            )
    print("procesado", os.path.basename(path), flush=True)

print(f"\nFilas totales: {n_rows:,}")
print("\n=== Detalles en Regular + CATIVO ===")
for det, st in sorted(stats.items(), key=lambda x: -x[1]["n"]):
    print(f"{det!r:40} n={st['n']:>9,} sum={st['sum']:>18,.1f} "
          f"min={st['min']:>15,.2f} max={st['max']:>18,.2f} "
          f"neg={st['neg']:>7,} cero={st['zero']:>7,} "
          f"unidades={len(unit_month[det]):,}")

print("\n=== Totales mensuales (unidades originales) para detalles de energia ===")
focus = [d for d in stats if "Energia" in d and "(kWh)" in d]
meses = sorted({m for d, m in month_tot if d in focus})
print("mes," + ",".join(focus))
for m in meses:
    print(m + "," + ",".join(f"{month_tot.get((d, m), 0):.0f}" for d in focus))

print("\n=== Suma por clase (periodo completo, GWh) ===")
for det in focus:
    print(f"\n{det}")
    for clase in sorted({c for c, d in class_tot if d == det}):
        tot = sum(class_tot[(clase, det)].values()) / 1e6
        if abs(tot) > 0:
            print(f"  {clase:22} {tot:12,.1f} GWh")

print("\n=== Combos detalle x clase (top 50) ===")
for (det, clase), n in combo_full.most_common(50):
    print(f"{n:>9,}  {det!r:38} | {clase!r}")
