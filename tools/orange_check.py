"""Verificacion independiente del clustering con Orange 3.

Se ejecuta en un entorno aparte que tenga Orange instalado:

    py -3.14 -m venv .venv-orange
    .venv-orange\\Scripts\\python -m pip install orange3
    .venv-orange\\Scripts\\python tools\\orange_check.py

1. Carga `aneel_orange_serie68_z.csv` (serie ya winsorizada y estandarizada por
   fila) y corre el k-Means de Orange con k=3. Compara con la particion del
   proyecto mediante ARI.
2. Repite el clustering sobre los 19 descriptores con normalizacion por columna
   de Orange, como control de una configuracion distinta.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, silhouette_score

from Orange.clustering.kmeans import KMeans
from Orange.data import ContinuousVariable, Domain, Table
from Orange.preprocess import Continuize, Normalizer

ROOT = Path(__file__).resolve().parents[1]
SERIE_Z = ROOT / "reports" / "orange" / "aneel_orange_serie68_z.csv"
ORANGE = ROOT / "reports" / "orange" / "aneel_orange.csv"
LABELS = ROOT / "reports" / "tables" / "final_labels.csv"
OUT = ROOT / "reports" / "tables" / "orange_verificacion.json"

DESCRIPTORES = [
    "cv", "tendencia_pct_mes", "tendencia_r2", "amplitud_estacional",
    "fuerza_estacionalidad", "ac1", "ac12", "yoy_media", "yoy_std",
    "drawdown_max", "rango_p90_p10", "iqr_relativo", "share_bajo_80",
    "share_alto_120", "crecimiento_12m", "pico_sin", "pico_cos",
    "valle_sin", "valle_cos",
]

MESES = [str(c) for c in pd.read_csv(SERIE_Z, nrows=0).columns
         if len(str(c)) == 7 and str(c)[4] == "-"]


def a_ari(labels_proyecto: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    ari = float(adjusted_rand_score(labels_proyecto, labels))
    tabla = pd.crosstab(labels_proyecto, labels)
    mapeo = {int(c): int(tabla[c].idxmax()) for c in tabla.columns}
    remapeado = np.array([mapeo[int(c)] for c in labels])
    return ari, float((remapeado == labels_proyecto).mean())


def main() -> None:
    final = pd.read_csv(LABELS).set_index("unidad")

    # --- 1. Replica del modelo final sobre la serie normalizada ---------------
    df = pd.read_csv(SERIE_Z)
    xz = df[MESES].to_numpy(dtype=float)
    domain = Domain([ContinuousVariable(f"M{i+1:02d}") for i in range(len(MESES))])
    table = Table.from_numpy(domain, xz)
    labels_serie = np.asarray(
        KMeans(n_clusters=3, n_init=10, random_state=42, preprocessors=[])(table)
    ).astype(int)
    labels_proyecto = final.loc[df["unidad"], "cluster"].to_numpy(dtype=int)

    ari_serie, match_serie = a_ari(labels_proyecto, labels_serie)

    # --- 2. Configuracion alternativa: descriptores + Normalize de Orange ----
    odf = pd.read_csv(ORANGE)
    odomain = Domain([ContinuousVariable(c) for c in DESCRIPTORES])
    otable = Table.from_numpy(odomain, odf[DESCRIPTORES].to_numpy(dtype=float))
    labels_desc = np.asarray(
        KMeans(n_clusters=3, n_init=10, random_state=42,
               preprocessors=[Continuize(), Normalizer()])(otable)
    ).astype(int)
    ari_desc, match_desc = a_ari(
        final.loc[odf["unidad"], "cluster"].to_numpy(dtype=int), labels_desc
    )

    resultado = {
        "python": platform.python_version(),
        "orange": __import__("Orange").__version__,
        "n_unidades": int(len(df)),
        "n_meses": int(len(MESES)),
        "replica_modelo_final": {
            "ari_vs_proyecto": round(ari_serie, 4),
            "coincidencia_tras_mapeo": round(match_serie, 4),
            "silhouette_orange": round(float(silhouette_score(xz, labels_serie)), 4),
            "silhouette_proyecto": round(float(silhouette_score(xz, labels_proyecto)), 4),
            "tamanos": {str(k): int(v) for k, v in
                        pd.Series(labels_serie).value_counts().sort_index().items()},
        },
        "alternativa_descriptores": {
            "representacion": "19 descriptores + Normalize (por columna, Orange)",
            "ari_vs_proyecto": round(ari_desc, 4),
            "coincidencia_tras_mapeo": round(match_desc, 4),
            "tamanos": {str(k): int(v) for k, v in
                        pd.Series(labels_desc).value_counts().sort_index().items()},
        },
        "nota": (
            "La replica exacta usa el mismo KMeans de scikit-learn que el pipeline; "
            "ARI=1 valida la exportacion normalizada y la configuracion, no un algoritmo "
            "distinto. La alternativa con descriptores es una representacion distinta y "
            "muestra cuanto cambia la particion."
        ),
    }
    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print("escrito", OUT)


if __name__ == "__main__":
    main()
