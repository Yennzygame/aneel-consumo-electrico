"""Diseno de Experimentos (DoE) para clustering de perfiles de consumo ANEEL.

Factores
--------
A. Representacion (features): serie68, estacional12, descriptores, PCA2/3.
B. Escalado / preprocesamiento: z por fila, log+z por fila, minmax por fila,
   z por columna, robust por columna, winsorizado, etc.
C. Algoritmo: K-Means, Ward, Average, Complete.
D. k: 2..8.

Para cada combinacion se calculan metricas en el espacio de clustering y en un
ESPACIO DE REFERENCIA COMUN (serie de 68 meses estandarizada por fila). Esto
permite comparar representaciones de distinta dimensionalidad sin favorecer
artificialmente a las de menos dimensiones.

Tambien se calcula estabilidad por submuestreo (80/20, 10 repeticiones): se
reentrena en el 80% y se asignan las unidades retenidas al centroide mas
cercano; se mide ARI contra la particion completa.

Uso:
    python -m src.doe --quick      # prueba rapida
    python -m src.doe --full       # DoE completo (~500 corridas)
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from src import config as C
from src.aneel_pipeline import (
    DESCRIPTORES_CLUSTER,
    col_minmax,
    col_robust,
    col_zscore,
    log_row_zscore,
    row_minmax,
    row_zscore,
)

# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def cargar_datos() -> dict[str, pd.DataFrame]:
    serie = pd.read_csv(C.PROCESSED_DIR / "matriz_serie68_mwh.csv", index_col=0)
    est = pd.read_csv(C.PROCESSED_DIR / "matriz_estacional12_mwh.csv", index_col=0)
    desc = pd.read_csv(C.PROCESSED_DIR / "descriptores.csv", index_col=0)
    pca_serie = pd.read_csv(C.PROCESSED_DIR / "pca_serie68.csv", index_col=0)

    # PCA del perfil estacional (se calcula una vez y se guarda)
    pca_est_path = C.PROCESSED_DIR / "pca_estacional12.csv"
    var_est_path = C.PROCESSED_DIR / "pca_estacional12_varianza.csv"
    if pca_est_path.exists():
        pca_est = pd.read_csv(pca_est_path, index_col=0)
    else:
        est_z = row_zscore(est)
        m = PCA(n_components=6, random_state=C.RANDOM_STATE)
        scores = m.fit_transform(est_z)
        pca_est = pd.DataFrame(
            scores, index=est.index, columns=[f"PC{i+1}" for i in range(scores.shape[1])]
        )
        pca_est.to_csv(pca_est_path, encoding="utf-8-sig")
        pd.DataFrame(
            {
                "componente": pca_est.columns,
                "varianza_explicada": m.explained_variance_ratio_,
                "acumulada": np.cumsum(m.explained_variance_ratio_),
            }
        ).to_csv(var_est_path, index=False, encoding="utf-8-sig")

    return {
        "serie68": serie,
        "estacional12": est,
        "descriptores": desc[DESCRIPTORES_CLUSTER].copy(),
        "pca2_serie": pca_serie[["PC1", "PC2"]].copy(),
        "pca3_serie": pca_serie[["PC1", "PC2", "PC3"]].copy(),
        "pca2_estacional": pca_est[["PC1", "PC2"]].copy(),
        "pca3_estacional": pca_est[["PC1", "PC2", "PC3"]].copy(),
    }


# ---------------------------------------------------------------------------
# Preprocesamientos
# ---------------------------------------------------------------------------


def winsor_fila(df: pd.DataFrame, q: float = 0.01) -> pd.DataFrame:
    lo = df.quantile(q, axis=1)
    hi = df.quantile(1 - q, axis=1)
    return df.clip(lower=lo, upper=hi, axis=0)


def winsor_columna(df: pd.DataFrame, q: float = 0.01) -> pd.DataFrame:
    lo = df.quantile(q, axis=0)
    hi = df.quantile(1 - q, axis=0)
    return df.clip(lower=lo, upper=hi, axis=1)


def aplicar_escalado(df: pd.DataFrame, escalado: str) -> pd.DataFrame:
    if escalado == "none":
        return df.copy()
    if escalado == "z_fila":
        return row_zscore(df)
    if escalado == "log_z_fila":
        return log_row_zscore(df)
    if escalado == "minmax_fila":
        return row_minmax(df)
    if escalado == "winsor_z_fila":
        return row_zscore(winsor_fila(df))
    if escalado == "z_columna":
        return col_zscore(df)
    if escalado == "robust_columna":
        return col_robust(df)
    if escalado == "minmax_columna":
        return col_minmax(df)
    if escalado == "winsor_z_columna":
        return col_zscore(winsor_columna(df))
    raise ValueError(f"Escalado desconocido: {escalado}")


# Combinaciones validas: no tiene sentido z-score por fila en descriptores.
REPRESENTACIONES: dict[str, list[str]] = {
    "serie68": ["z_fila", "log_z_fila", "minmax_fila", "winsor_z_fila", "z_columna"],
    "estacional12": ["z_fila", "log_z_fila", "minmax_fila", "winsor_z_fila", "z_columna"],
    "descriptores": ["z_columna", "robust_columna", "minmax_columna", "winsor_z_columna"],
    "pca2_serie": ["none"],
    "pca3_serie": ["none"],
    "pca2_estacional": ["none"],
    "pca3_estacional": ["none"],
}

ALGORITMOS = ["kmeans", "ward", "average", "complete"]
K_VALUES = C.K_RANGE


def construir_pipeline(rep: str, esc: str, datos: dict[str, pd.DataFrame]):
    X = aplicar_escalado(datos[rep], esc)
    return X


# ---------------------------------------------------------------------------
# Modelos y metricas
# ---------------------------------------------------------------------------


def ajustar(X: np.ndarray, algoritmo: str, k: int, seed: int = C.RANDOM_STATE):
    if algoritmo == "kmeans":
        m = KMeans(n_clusters=k, n_init=10, random_state=seed)
        labels = m.fit_predict(X)
        return labels, m.inertia_
    if algoritmo == "ward":
        m = AgglomerativeClustering(n_clusters=k, linkage="ward")
    elif algoritmo == "average":
        m = AgglomerativeClustering(n_clusters=k, linkage="average", metric="euclidean")
    elif algoritmo == "complete":
        m = AgglomerativeClustering(n_clusters=k, linkage="complete", metric="euclidean")
    else:
        raise ValueError(algoritmo)
    labels = m.fit_predict(X)
    # SSE para algoritmos sin inercia
    sse = 0.0
    for c in np.unique(labels):
        Xc = X[labels == c]
        sse += float(((Xc - Xc.mean(axis=0)) ** 2).sum())
    return labels, sse


def centroides(X: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    clases = np.unique(labels)
    cent = np.vstack([X[labels == c].mean(axis=0) for c in clases])
    return cent, clases


def asignar_centroide(X: np.ndarray, cent: np.ndarray, clases: np.ndarray) -> np.ndarray:
    # distancias euclidianas al cuadrado sin crear tensor 3D
    d = (
        (X**2).sum(axis=1)[:, None]
        - 2 * X @ cent.T
        + (cent**2).sum(axis=1)[None, :]
    )
    return clases[np.argmin(d, axis=1)]


def metricas_particion(
    X: np.ndarray,
    labels: np.ndarray,
    X_ref: np.ndarray,
    X_ref_pca: np.ndarray,
    inercia: float,
) -> dict:
    clases, counts = np.unique(labels, return_counts=True)
    n = len(labels)
    if len(clases) < 2 or len(clases) >= n:
        return {}
    sizes = counts.astype(float)
    return {
        "silhouette_espacio": float(silhouette_score(X, labels)),
        "davies_bouldin_espacio": float(davies_bouldin_score(X, labels)),
        "calinski_espacio": float(calinski_harabasz_score(X, labels)),
        "inercia": float(inercia),
        "silhouette_ref": float(silhouette_score(X_ref, labels)),
        "davies_bouldin_ref": float(davies_bouldin_score(X_ref, labels)),
        "calinski_ref": float(calinski_harabasz_score(X_ref, labels)),
        "silhouette_ref_pca10": float(silhouette_score(X_ref_pca, labels)),
        "min_cluster_share": float(sizes.min() / n),
        "max_cluster_share": float(sizes.max() / n),
        "balance": float(sizes.min() / sizes.max()),
        "n_singletons": int((sizes == 1).sum()),
    }


def estabilidad_submuestreo(
    X: np.ndarray,
    algoritmo: str,
    k: int,
    labels_full: np.ndarray,
    n_rep: int = 10,
    frac: float = 0.8,
    seed: int = C.RANDOM_STATE,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(labels_full)
    aris = []
    for r in range(n_rep):
        idx = rng.permutation(n)
        n_train = int(frac * n)
        tr, te = idx[:n_train], idx[n_train:]
        labels_tr, _ = ajustar(X[tr], algoritmo, k, seed=seed + r)
        cent, clases = centroides(X[tr], labels_tr)
        labels_te = asignar_centroide(X[te], cent, clases)
        aris.append(adjusted_rand_score(labels_full[te], labels_te))
    return float(np.mean(aris)), float(np.std(aris))


def estabilidad_semilla(
    X: np.ndarray, k: int, labels_full: np.ndarray, n_rep: int = 5
) -> float:
    aris = []
    for r in range(n_rep):
        lab, _ = ajustar(X, "kmeans", k, seed=C.RANDOM_STATE + 100 + r)
        aris.append(adjusted_rand_score(labels_full, lab))
    return float(np.mean(aris))


# ---------------------------------------------------------------------------
# MLflow
# ---------------------------------------------------------------------------


def preparar_mlflow():
    mlflow.set_tracking_uri(f"sqlite:///{C.MLFLOW_DB.as_posix()}")
    mlflow.set_registry_uri(f"sqlite:///{C.MLFLOW_DB.as_posix()}")
    client = mlflow.tracking.MlflowClient()
    exp = client.get_experiment_by_name(C.EXPERIMENTO_DOE)
    if exp is None:
        exp_id = client.create_experiment(
            C.EXPERIMENTO_DOE,
            artifact_location=C.MLARTIFACTS_DIR.as_uri(),
        )
    else:
        exp_id = exp.experiment_id
    mlflow.set_experiment(experiment_id=exp_id)
    return exp_id


# ---------------------------------------------------------------------------
# Ejecucion
# ---------------------------------------------------------------------------


def ejecutar(
    quick: bool = False,
    max_runs: int | None = None,
    n_estab: int = 10,
    force: bool = False,
) -> pd.DataFrame:
    out = C.TABLES_DIR / ("doe_resultados_quick.csv" if quick else "doe_resultados.csv")
    if out.exists() and not force:
        print(f"[doe] ya existe {out}")
        return pd.read_csv(out)

    datos = cargar_datos()
    unidades = datos["serie68"].index
    X_ref_df = row_zscore(datos["serie68"])
    X_ref = X_ref_df.to_numpy(dtype=float)
    pca_ref = PCA(n_components=10, random_state=C.RANDOM_STATE)
    X_ref_pca = pca_ref.fit_transform(X_ref)

    reps = list(REPRESENTACIONES)
    algos = ALGORITMOS
    ks = K_VALUES
    if quick:
        reps = ["serie68", "estacional12", "descriptores"]
        algos = ["kmeans", "ward"]
        ks = [2, 3, 4]
        n_estab = max(3, n_estab // 2)

    combinaciones = [
        (rep, esc, algo, k)
        for rep in reps
        for esc in REPRESENTACIONES[rep]
        for algo in algos
        for k in ks
    ]
    if max_runs:
        combinaciones = combinaciones[:max_runs]

    print(
        f"[doe] combinaciones={len(combinaciones):,} | estabilidad={n_estab} rep | "
        f"n={len(unidades)}"
    )
    preparar_mlflow()
    resultados = []
    labels_store = {}
    t0 = time.time()

    for i, (rep, esc, algo, k) in enumerate(combinaciones, 1):
        X_df = construir_pipeline(rep, esc, datos)
        X = X_df.to_numpy(dtype=float)
        run_key = f"{rep}|{esc}|{algo}|k{k}"

        labels, inercia = ajustar(X, algo, k)
        met = metricas_particion(X, labels, X_ref, X_ref_pca, inercia)
        if not met:
            continue
        estab, estab_std = estabilidad_submuestreo(
            X, algo, k, labels, n_rep=n_estab
        )
        estab_seed = (
            estabilidad_semilla(X, k, labels) if algo == "kmeans" else np.nan
        )

        met.update(
            {
                "estabilidad_media": estab,
                "estabilidad_std": estab_std,
                "estabilidad_semilla": estab_seed,
            }
        )
        fila = {
            "run_key": run_key,
            "representacion": rep,
            "escalado": esc,
            "algoritmo": algo,
            "k": k,
            "n_features": X.shape[1],
            "n_samples": X.shape[0],
        }
        fila.update(met)
        resultados.append(fila)
        labels_store[run_key] = labels.astype(np.int16)

        with mlflow.start_run(run_name=run_key) as run:
            mlflow.set_tags(
                {
                    "etapa": "doe",
                    "run_key": run_key,
                    "representacion": rep,
                    "escalado": esc,
                    "algoritmo": algo,
                }
            )
            mlflow.log_params(
                {
                    "representacion": rep,
                    "escalado": esc,
                    "algoritmo": algo,
                    "k": k,
                    "n_features": X.shape[1],
                    "n_samples": X.shape[0],
                    "random_state": C.RANDOM_STATE,
                    "n_estabilidad": n_estab,
                }
            )
            mlflow.log_metrics({k2: float(v) for k2, v in met.items()})

        if i % 20 == 0 or i == len(combinaciones):
            elapsed = time.time() - t0
            eta = elapsed / i * (len(combinaciones) - i)
            print(
                f"[doe] {i}/{len(combinaciones)} ({100*i/len(combinaciones):.1f}%) | "
                f"sil_ref={met['silhouette_ref']:.4f} | estab={estab:.3f} | "
                f"ETA {eta/60:.1f} min",
                flush=True,
            )

    df = pd.DataFrame(resultados).sort_values(
        ["silhouette_ref", "estabilidad_media"], ascending=False
    )
    df.to_csv(out, index=False, encoding="utf-8-sig")
    np.savez_compressed(
        C.TABLES_DIR / ("etiquetas_doe_quick.npz" if quick else "etiquetas_doe.npz"),
        **labels_store,
    )
    print(f"[doe] listo en {(time.time()-t0)/60:.1f} min -> {out}")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--max-runs", type=int, default=None)
    ap.add_argument("--n-estab", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    quick = args.quick and not args.full
    ejecutar(
        quick=quick,
        max_runs=args.max_runs,
        n_estab=args.n_estab,
        force=args.force,
    )


if __name__ == "__main__":
    main()
