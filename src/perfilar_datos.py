"""Perfilado rapido de los CSV crudos de ANEEL/SAMP.

Lee por chunks y acumula:
  - cardinalidad y frecuencias de columnas categoricas clave
  - cobertura temporal (DatCompetencia)
  - diagnostico del formato numerico de VlrMercado
  - combinaciones NomTipoMercado x DscDetalheMercado
No carga todo el dataset en memoria.
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter, defaultdict

import pandas as pd

RAW_DIR = r"C:\Users\yennz\OneDrive\Documentos\Ciencia de Datos\data\raw"
OUT_DIR = r"C:\Users\yennz\OneDrive\Documentos\Ciencia de Datos\reports\diagnostico"
os.makedirs(OUT_DIR, exist_ok=True)

CAT_COLS = [
    "NomTipoMercado",
    "DscModalidadeTarifaria",
    "DscSubGrupoTarifario",
    "DscClasseConsumoMercado",
    "DscSubClasseConsumidor",
    "DscDetalheConsumidor",
    "DscPostoTarifario",
    "DscOpcaoEnergia",
    "DscDetalheMercado",
    "SigAgenteDistribuidora",
]
USE = ["DatCompetencia", "VlrMercado"] + CAT_COLS

counters = {c: Counter() for c in CAT_COLS}
month_counter = Counter()
combo_counter = Counter()
n_rows = 0
n_bad_num = 0
fmt_counter = Counter()
per_file = {}
neg_rows = 0

num_re = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+(,\d+)?$")


def parse_br(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    # quita separador de miles solo cuando hay coma decimal
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma, s.str.replace(".", "", regex=False))
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


for path in sorted(glob.glob(os.path.join(RAW_DIR, "samp-*.csv"))):
    name = os.path.basename(path)
    f_rows = 0
    for chunk in pd.read_csv(
        path, sep=";", encoding="latin1", usecols=USE, chunksize=400_000,
        dtype=str, low_memory=False,
    ):
        f_rows += len(chunk)
        n_rows += len(chunk)
        for c in CAT_COLS:
            counters[c].update(chunk[c].fillna("<NA>").str.strip())

        comp = chunk["DatCompetencia"].fillna("<NA>").str.strip()
        month_counter.update(comp)

        det = chunk["DscDetalheMercado"].fillna("<NA>").str.strip()
        tipo = chunk["NomTipoMercado"].fillna("<NA>").str.strip()
        combo_counter.update(zip(tipo, det))

        raw = chunk["VlrMercado"].fillna("<NA>").astype(str).str.strip()
        fmt_counter.update(
            ["vacio" if (raw == "<NA>").all() else "con_valor"]
        )
        fmt_counter["con_coma"] += int(raw.str.contains(",", regex=False).sum())
        fmt_counter["con_punto"] += int(raw.str.contains(".", regex=False).sum())
        fmt_counter["formato_invalido"] += int((~raw.str.match(num_re) & (raw != "<NA>")).sum())

        vals = parse_br(chunk["VlrMercado"])
        n_bad_num += int(vals.isna().sum())
        neg_rows += int((vals < 0).sum())

    per_file[name] = f_rows
    print(f"{name}: {f_rows:,} filas", flush=True)

resumen = {
    "total_filas": n_rows,
    "filas_por_archivo": per_file,
    "valores_no_numericos": n_bad_num,
    "filas_valor_negativo": neg_rows,
    "formato_vlmercado": dict(fmt_counter),
    "meses": {
        "min": min(month_counter),
        "max": max(month_counter),
        "n_meses_distintos": len(month_counter),
        "conteo_por_mes": dict(sorted(month_counter.items())),
    },
    "cardinalidades": {c: len(counters[c]) for c in CAT_COLS},
    "frecuencias": {c: counters[c].most_common(60) for c in CAT_COLS},
    "combinaciones_tipo_detalle": [
        {"tipo": k[0], "detalle": k[1], "filas": v}
        for k, v in combo_counter.most_common(80)
    ],
}

with open(os.path.join(OUT_DIR, "perfil_datos.json"), "w", encoding="utf-8") as f:
    json.dump(resumen, f, ensure_ascii=False, indent=2)

print("\n=== RESUMEN ===")
print("Filas:", f"{n_rows:,}")
print("Meses:", resumen["meses"]["min"], "a", resumen["meses"]["max"], "|", len(month_counter))
print("No numericos:", n_bad_num, "| negativos:", neg_rows)
print("Formato:", dict(fmt_counter))
print("\nCardinalidades:", resumen["cardinalidades"])
print("\nTipoMercado:")
for k, v in counters["NomTipoMercado"].most_common(20):
    print(f"  {k!r}: {v:,}")
print("\nDetalleMercado:")
for k, v in counters["DscDetalheMercado"].most_common(30):
    print(f"  {k!r}: {v:,}")
print("\nClases:")
for k, v in counters["DscClasseConsumoMercado"].most_common(20):
    print(f"  {k!r}: {v:,}")
print("\nOpcionEnergia:")
for k, v in counters["DscOpcaoEnergia"].most_common(10):
    print(f"  {k!r}: {v:,}")
print("\nCombinaciones tipo/detalle (top 40):")
for k, v in combo_counter.most_common(40):
    print(f"  {v:>9,}  {k[0]!r:45} | {k[1]!r}")
