"""Seleccion del modelo final, caracterizacion y artefactos de decision.

Entradas : reports/tables/doe_resultados.csv
Salidas  : reports/tables/final_*.csv, reports/figures/*.png,
           reports/orange/aneel_orange.csv, models/modelo_final.joblib

Uso:
    python -m src.select_final --run-key "serie68|z_fila|kmeans|k3"
    python -m src.select_final --auto
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy.stats import chi2_contingency, kruskal
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_samples, silhouette_score
from sklearn.cluster import KMeans

from src import config as C
from src.aneel_pipeline import DESCRIPTORES_CLUSTER, row_zscore
from src.doe import (
    ajustar,
    asignar_centroide,
    cargar_datos,
    centroides,
    construir_pipeline,
    estabilidad_submuestreo,
)

plt.rcParams.update(
    {
        "figure.dpi": 120,
        "savefig.dpi": 220,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

PALETA = [
    "#2E86AB",
    "#E4572E",
    "#28A745",
    "#6C5B7B",
    "#F4A261",
    "#17A2B8",
    "#6C757D",
]


# ---------------------------------------------------------------------------
# Utilidades estadisticas
# ---------------------------------------------------------------------------


def cramers_v(x: pd.Series, y: pd.Series) -> tuple[float, float, pd.DataFrame]:
    tabla = pd.crosstab(x, y)
    if tabla.shape[0] < 2 or tabla.shape[1] < 2:
        return np.nan, np.nan, tabla
    chi2, p, dof, _ = chi2_contingency(tabla)
    n = tabla.to_numpy().sum()
    v = np.sqrt(chi2 / (n * (min(tabla.shape) - 1)))
    return float(v), float(p), tabla


def bh_fdr(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, idx in enumerate(order[::-1], start=1):
        val = min(prev, p[idx] * n / (n - rank + 1))
        q[idx] = val
        prev = val
    return q.tolist()


# ---------------------------------------------------------------------------
# Seleccion
# ---------------------------------------------------------------------------


def puntuar_doe(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    # Filtros de interpretabilidad y calidad minima
    d = d[(d["k"] >= 3) & (d["k"] <= 6)]
    d = d[d["min_cluster_share"] >= 0.03]
    d = d[d["n_singletons"] == 0]
    d = d[d["silhouette_ref"] >= 0.10]
    if d.empty:
        d = df.copy()

    def pct(s: pd.Series, ascending: bool = True) -> pd.Series:
        return s.rank(pct=True, ascending=ascending).fillna(0.0)

    d["s_sil"] = pct(d["silhouette_ref"], ascending=True)
    d["s_db"] = pct(-d["davies_bouldin_ref"], ascending=True)
    d["s_ch"] = pct(d["calinski_ref"], ascending=True)
    d["s_est"] = pct(d["estabilidad_media"], ascending=True)
    d["s_bal"] = pct(d["balance"], ascending=True)
    d["s_pars"] = 1 - (d["k"] - 3) / 3
    d["score"] = (
        0.35 * d["s_sil"]
        + 0.15 * d["s_db"]
        + 0.10 * d["s_ch"]
        + 0.25 * d["s_est"]
        + 0.10 * d["s_bal"]
        + 0.05 * d["s_pars"]
    )
    return d.sort_values("score", ascending=False)


def refit(run_key: str, datos: dict[str, pd.DataFrame]):
    rep, esc, algo, kk = run_key.split("|")
    k = int(kk[1:])
    X = construir_pipeline(rep, esc, datos)
    labels, inercia = ajustar(X.to_numpy(dtype=float), algo, k)
    return X, labels, inercia, rep, esc, algo, k


# ---------------------------------------------------------------------------
# Nombres de clusters
# ---------------------------------------------------------------------------


def nombrar_clusters(perfil: pd.DataFrame) -> dict[int, str]:
    """Nombres basados en la evidencia, no en supuestos previos.

    Orden de decision:
      1. Contraccion sostenida: tendencia negativa fuerte y crecimiento negativo.
      2. Crecimiento acelerado: mayor crecimiento entre los clusters restantes.
      3. Estacional-volatil: mayor volatilidad entre los restantes.
      4. Base estable: el resto.
    """
    vol = perfil["cv"].rank(pct=True) + perfil["amplitud_estacional"].rank(pct=True)
    nombres: dict[int, str] = {}
    restantes = list(perfil.index)

    idx = int(perfil["tendencia_pct_mes"].idxmin())
    if (
        perfil.loc[idx, "tendencia_pct_mes"] < -0.50
        and perfil.loc[idx, "crecimiento_12m"] < -0.10
    ):
        nombres[idx] = "Contracción sostenida"
        restantes.remove(idx)

    if restantes:
        idx = int(perfil.loc[restantes, "crecimiento_12m"].idxmax())
        if perfil.loc[idx, "crecimiento_12m"] > 0.10:
            nombres[idx] = "Crecimiento acelerado"
            restantes.remove(idx)

    # Solo asignar "Estacional-volatil" si quedan al menos dos clusters por
    # nombrar; con k=3 el cluster restante es la base estable.
    if len(restantes) > 1:
        idx = int(vol.loc[restantes].idxmax())
        nombres[idx] = "Estacional-volátil"
        restantes.remove(idx)

    for i in restantes:
        nombres[int(i)] = "Base estable"
    return nombres


# ---------------------------------------------------------------------------
# Graficos
# ---------------------------------------------------------------------------


def guardar(fig, nombre: str) -> None:
    path = C.FIGURES_DIR / nombre
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig] {path.name}")


def fig_cobertura() -> None:
    panel = pd.read_csv(C.PROCESSED_DIR / "painel_mensal.csv")
    total = panel.groupby("mes")["consumo_mwh"].sum().sort_index()
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = pd.PeriodIndex(total.index, freq="M").to_timestamp()
    ax.plot(x, total.values / 1e6, marker="o", ms=3, lw=1.8, color="#1f4e79")
    ax.set_title("Consumo mensual del mercado cativo regular (SAMP/ANEEL)")
    ax.set_ylabel("TWh/mes")
    ax.set_xlabel("Mes de competencia")
    ax.axvspan(
        pd.Timestamp("2026-09-01"),
        pd.Timestamp("2026-09-28"),
        color="#E4572E",
        alpha=0.18,
        label="2026-09 parcial (excluido)",
    )
    ax.legend(frameon=False, loc="lower left")
    guardar(fig, "01_cobertura_temporal.png")


def fig_unidades(meta: pd.DataFrame, labels: pd.Series) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    ax = axes[0]
    ax.hist(np.log10(meta.loc[labels.index, "total_mwh"]), bins=35, color="#2E86AB")
    ax.set_title("Tamano de los segmentos")
    ax.set_xlabel("log10(MWh totales 2021-2026)")
    ax.set_ylabel("Numero de segmentos")
    ax = axes[1]
    counts = meta.loc[labels.index].groupby("clase").size().sort_values()
    ax.barh(counts.index, counts.values, color="#E4572E")
    ax.set_title("Segmentos por clase de consumo")
    ax.set_xlabel("Numero de segmentos")
    guardar(fig, "02_unidades.png")


def fig_doe(df: pd.DataFrame, final_key: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    reps = list(df["representacion"].unique())
    markers = {"kmeans": "o", "ward": "s", "average": "^", "complete": "D"}
    for r, rep in enumerate(reps):
        sub = df[df["representacion"] == rep]
        for algo in markers:
            s2 = sub[sub["algoritmo"] == algo]
            if s2.empty:
                continue
            ax.scatter(
                s2["silhouette_ref"],
                s2["estabilidad_media"],
                s=18 + 6 * s2["k"],
                c=[PALETA[r % len(PALETA)]],
                marker=markers[algo],
                alpha=0.55,
                edgecolors="none",
            )
    top = df[df["run_key"] == final_key]
    if not top.empty:
        ax.scatter(
            top["silhouette_ref"],
            top["estabilidad_media"],
            s=260,
            facecolors="none",
            edgecolors="black",
            linewidths=2,
            zorder=5,
        )
        ax.annotate(
            "modelo final",
            (float(top["silhouette_ref"].iloc[0]), float(top["estabilidad_media"].iloc[0])),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=9,
            fontweight="bold",
        )
    ax.set_xlabel("Silhouette en espacio de referencia (68 meses)")
    ax.set_ylabel("Estabilidad por submuestreo (ARI medio)")
    ax.set_title("DoE: calidad vs estabilidad de las 504 configuraciones")

    handles_rep = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETA[i % len(PALETA)],
               markersize=8, label=rep)
        for i, rep in enumerate(reps)
    ]
    handles_algo = [
        Line2D([0], [0], marker=m, color="gray", linestyle="None", markersize=7,
               label=algo)
        for algo, m in markers.items()
    ]
    leg1 = ax.legend(handles=handles_rep, title="Representacion", fontsize=7,
                     title_fontsize=7, frameon=False, loc="lower right", ncol=2)
    ax.add_artist(leg1)
    ax.legend(handles=handles_algo, title="Algoritmo", fontsize=7,
              title_fontsize=7, frameon=False, loc="upper left")
    guardar(fig, "03_doe_calidad_estabilidad.png")

    # Heatmap resumen por representacion y k (mejor score por celda)
    piv = (
        df.groupby(["representacion", "k"])["silhouette_ref"]
        .max()
        .unstack(fill_value=np.nan)
    )
    fig, ax = plt.subplots(figsize=(8, 4.2))
    im = ax.imshow(piv.values, aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), piv.index)
    ax.set_xlabel("k")
    ax.set_title("Mejor silhouette de referencia por representacion y k")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    guardar(fig, "04_doe_heatmap.png")


def fig_curva_k(df: pd.DataFrame, run_key: str) -> None:
    rep, esc, algo, _ = run_key.split("|")
    sub = df[
        (df["representacion"] == rep)
        & (df["escalado"] == esc)
        & (df["algoritmo"] == algo)
    ].sort_values("k")
    if sub.empty:
        return
    fig, ax1 = plt.subplots(figsize=(8, 4.6))
    ax1.plot(sub["k"], sub["inercia"], marker="o", color="#1f4e79", label="Inercia (WCSS)")
    ax1.set_xlabel("Numero de clusters k")
    ax1.set_ylabel("Inercia", color="#1f4e79")
    ax1.tick_params(axis="y", labelcolor="#1f4e79")
    ax2 = ax1.twinx()
    ax2.plot(sub["k"], sub["silhouette_ref"], marker="s", color="#E4572E",
             label="Silhouette ref.")
    ax2.plot(sub["k"], sub["davies_bouldin_ref"], marker="^", color="#6C5B7B",
             linestyle="--", label="Davies-Bouldin ref.")
    ax2.set_ylabel("Silhouette / Davies-Bouldin")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [l.get_label() for l in lines], frameon=False, fontsize=8)
    ax1.set_title(f"Seleccion de k: {rep} / {esc} / {algo}")
    guardar(fig, "05_curva_k.png")


def fig_silueta(X: np.ndarray, labels: np.ndarray, nombres: dict[int, str]) -> None:
    sil = silhouette_samples(X, labels)
    media = silhouette_score(X, labels)
    fig, ax = plt.subplots(figsize=(8, 5))
    y = 10
    yticks, ylabels = [], []
    for c in np.unique(labels):
        vals = np.sort(sil[labels == c])
        ax.fill_betweenx(
            np.arange(y, y + len(vals)), 0, vals,
            color=PALETA[int(c) % len(PALETA)], alpha=0.8,
        )
        ax.text(-0.03, y + len(vals) / 2, nombres.get(int(c), f"C{c}"),
                ha="right", va="center", fontsize=9)
        yticks.append(y + len(vals) / 2)
        ylabels.append("")
        y += len(vals) + 10
    ax.axvline(media, color="black", linestyle="--", lw=1.2)
    ax.set_yticks([])
    ax.set_xlim(min(-0.08, float(sil.min()) - 0.03), 1.0)
    ax.set_xlabel("Coeficiente de silueta")
    ax.set_title(f"Silueta por cluster (promedio = {media:.3f})")
    guardar(fig, "06_silueta.png")


def fig_pca(labels: pd.Series, nombres: dict[int, str], pca: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 6))
    for c in sorted(labels.unique()):
        idx = labels[labels == c].index
        ax.scatter(
            pca.loc[idx, "PC1"], pca.loc[idx, "PC2"],
            s=26, alpha=0.7, label=f"{nombres.get(int(c), c)} (n={len(idx)})",
            color=PALETA[int(c) % len(PALETA)], edgecolors="white", linewidths=0.3,
        )
        cx, cy = pca.loc[idx, "PC1"].mean(), pca.loc[idx, "PC2"].mean()
        ax.scatter(cx, cy, marker="X", s=180, color=PALETA[int(c) % len(PALETA)],
                   edgecolors="black", linewidths=1.2, zorder=5)
    ax.set_xlabel(f"PC1 ({pca.attrs.get('var1', '')})")
    ax.set_ylabel(f"PC2 ({pca.attrs.get('var2', '')})")
    ax.set_title("Proyeccion PCA de la forma de la curva (PC1 vs PC2)")
    ax.legend(frameon=False, fontsize=8)
    guardar(fig, "07_pca_scatter.png")


def fig_centroides(serie: pd.DataFrame, labels: pd.Series, nombres: dict[int, str]) -> None:
    z = row_zscore(serie)
    z["cluster"] = labels.reindex(z.index)
    perfil = z.groupby("cluster").mean()
    orden = sorted(perfil.index, key=lambda c: nombres.get(int(c), str(c)))
    perfil = perfil.loc[orden]
    meses = pd.PeriodIndex(perfil.columns, freq="M").to_timestamp()

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    for c in orden:
        ax.plot(meses, perfil.loc[c].values, lw=1.8,
                label=nombres.get(int(c), c), color=PALETA[int(c) % len(PALETA)])
    ax.set_title("Forma media estandarizada por cluster")
    ax.set_ylabel("Z-score del consumo mensual")
    ax.legend(frameon=False, fontsize=8)
    ax.tick_params(axis="x", rotation=45)

    ax = axes[1]
    raw = serie.copy()
    raw["cluster"] = labels.reindex(raw.index)
    media = raw.groupby("cluster").mean()
    for c in orden:
        idx = media.loc[c] / media.loc[c].mean() * 100
        ax.plot(meses, idx.values, lw=1.8,
                label=nombres.get(int(c), c), color=PALETA[int(c) % len(PALETA)])
    ax.axhline(100, color="black", lw=0.8, ls=":")
    ax.set_title("Perfil medio indexado (base = 100)")
    ax.set_ylabel("Indice de consumo")
    ax.tick_params(axis="x", rotation=45)
    guardar(fig, "08_centroides.png")


def fig_descriptores(desc: pd.DataFrame, labels: pd.Series, nombres: dict[int, str]) -> None:
    cols = [
        ("cv", "Coeficiente de variacion"),
        ("tendencia_pct_mes", "Tendencia (% del nivel medio por mes)"),
        ("amplitud_estacional", "Amplitud estacional"),
        ("crecimiento_12m", "Crecimiento ultimos 12 vs primeros 12 meses"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (col, titulo) in zip(axes.ravel(), cols):
        data = []
        etiquetas = []
        for c in sorted(labels.unique()):
            vals = desc.loc[labels[labels == c].index, col].dropna().values
            data.append(vals)
            etiquetas.append(nombres.get(int(c), str(c)))
        bp = ax.boxplot(data, patch_artist=True, widths=0.55, showfliers=False)
        for patch, c in zip(bp["boxes"], sorted(labels.unique())):
            patch.set_facecolor(PALETA[int(c) % len(PALETA)])
            patch.set_alpha(0.75)
        ax.set_xticks(range(1, len(etiquetas) + 1), etiquetas, rotation=15, fontsize=8)
        ax.set_title(titulo)
    fig.suptitle("Descriptores de forma por arquetipo", fontweight="bold")
    fig.tight_layout()
    guardar(fig, "09_descriptores.png")


def fig_clases(labels: pd.Series, meta: pd.DataFrame, nombres: dict[int, str]) -> None:
    df = meta.loc[labels.index].copy()
    df["cluster"] = labels
    df["cluster_nombre"] = df["cluster"].map(nombres)

    comp = pd.crosstab(df["cluster_nombre"], df["clase"], normalize="index") * 100
    mwh = (
        df.pivot_table(index="cluster_nombre", columns="clase", values="total_mwh",
                       aggfunc="sum")
        .div(df.groupby("cluster_nombre")["total_mwh"].sum(), axis=0)
        * 100
    )
    orden = [nombres[int(c)] for c in sorted(labels.unique())]
    comp = comp.reindex(orden)
    mwh = mwh.reindex(orden)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))
    cmap = plt.get_cmap("tab20")
    for ax, tabla, titulo in [
        (axes[0], comp, "% de segmentos por clase"),
        (axes[1], mwh, "% de MWh por clase"),
    ]:
        bottom = np.zeros(len(tabla))
        for j, col in enumerate(tabla.columns):
            ax.bar(tabla.index, tabla[col].values, bottom=bottom, label=col,
                   color=cmap(j % 20), edgecolor="white", linewidth=0.4)
            bottom += tabla[col].values
        ax.set_title(titulo)
        ax.set_ylabel("%")
        ax.tick_params(axis="x", rotation=15)
    axes[1].legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False, fontsize=8)
    guardar(fig, "10_composicion_clases.png")


def fig_exposicion(expo: pd.DataFrame, labels: pd.Series, nombres: dict[int, str]) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    colores = [PALETA[int(c) % len(PALETA)] for c in expo["cluster_dominante"]]
    ax.scatter(
        expo["tendencia_ponderada"], expo["cv_ponderado"],
        s=20 + 18 * np.log1p(expo["total_mwh"] / 1e5),
        c=colores, alpha=0.75, edgecolors="white", linewidths=0.5,
    )
    ax.axvline(expo["tendencia_ponderada"].median(), color="gray", ls="--", lw=0.8)
    ax.axhline(expo["cv_ponderado"].median(), color="gray", ls="--", lw=0.8)
    for agente, row in expo.nlargest(12, "total_mwh").iterrows():
        ax.annotate(agente, (row["tendencia_ponderada"], row["cv_ponderado"]),
                    fontsize=7, xytext=(3, 3), textcoords="offset points")
    handles = [
        Line2D([0], [0], marker="o", color="w", label=nombres.get(int(c), str(c)),
               markerfacecolor=PALETA[int(c) % len(PALETA)], markersize=8)
        for c in sorted(labels.unique())
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="best")
    ax.set_xlabel("Tendencia ponderada por MWh (% del nivel medio por mes)")
    ax.set_ylabel("Coeficiente de variacion ponderado")
    ax.set_title("Mapa de exposicion de las distribuidoras")
    guardar(fig, "11_exposicion_distribuidoras.png")


def fig_estabilidad(aris: np.ndarray, media: float) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.hist(aris, bins=20, color="#2E86AB", edgecolor="white")
    ax.axvline(media, color="#E4572E", lw=2, ls="--",
               label=f"media = {media:.3f}")
    ax.set_xlabel("ARI entre la particion completa y la de submuestra")
    ax.set_ylabel("Frecuencia")
    ax.set_title("Estabilidad del modelo final (100 submuestras 80/20)")
    ax.legend(frameon=False)
    guardar(fig, "12_estabilidad.png")


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


def ejecutar(run_key: str | None = None, auto: bool = True) -> dict:
    res = pd.read_csv(C.TABLES_DIR / "doe_resultados.csv")
    scored = puntuar_doe(res)
    scored.to_csv(C.TABLES_DIR / "doe_ranking.csv", index=False, encoding="utf-8-sig")
    scored.head(20).to_csv(
        C.TABLES_DIR / "doe_top20.csv", index=False, encoding="utf-8-sig"
    )
    if run_key is None:
        if not auto:
            print(scored.head(15)[["run_key", "score", "silhouette_ref",
                                   "estabilidad_media", "k"]].to_string(index=False))
            raise SystemExit("Indique --run-key")
        run_key = str(scored.iloc[0]["run_key"])

    print(f"[final] run_key = {run_key}")
    datos = cargar_datos()
    serie = datos["serie68"]
    meta = pd.read_csv(C.PROCESSED_DIR / "unidades_meta.csv", index_col=0)
    # Descriptores completos (incluyen agente, clase y tamano para interpretar;
    # el clustering usa solo DESCRIPTORES_CLUSTER via datos["descriptores"]).
    desc = pd.read_csv(C.PROCESSED_DIR / "descriptores.csv", index_col=0)
    pca = pd.read_csv(C.PROCESSED_DIR / "pca_serie68.csv", index_col=0)
    var = pd.read_csv(C.PROCESSED_DIR / "pca_varianza.csv")
    pca.attrs["var1"] = f"{var.loc[0, 'varianza_explicada']*100:.1f}% var."
    pca.attrs["var2"] = f"{var.loc[1, 'varianza_explicada']*100:.1f}% var."

    X, labels, inercia, rep, esc, algo, k = refit(run_key, datos)
    labels = pd.Series(labels, index=X.index, name="cluster")

    # Perfil por cluster
    df = desc.copy()
    df["cluster"] = labels
    perfil = df.groupby("cluster").agg(
        n_unidades=("cv", "size"),
        cv=("cv", "mean"),
        tendencia_pct_mes=("tendencia_pct_mes", "mean"),
        amplitud_estacional=("amplitud_estacional", "mean"),
        fuerza_estacionalidad=("fuerza_estacionalidad", "mean"),
        crecimiento_12m=("crecimiento_12m", "mean"),
        ac12=("ac12", "mean"),
        yoy_std=("yoy_std", "mean"),
    )
    perfil["total_mwh"] = df.groupby("cluster")["total_mwh"].sum()
    perfil["share_mwh"] = perfil["total_mwh"] / perfil["total_mwh"].sum()
    perfil["consumidores"] = df.groupby("cluster")["consumidores_medios"].sum()
    nombres = nombrar_clusters(perfil)
    perfil["nombre"] = perfil.index.map(nombres)

    # Tabla de clusters
    tabla = perfil.copy()
    tabla["clases_top"] = [
        ", ".join(
            f"{c} ({v}%)"
            for c, v in (
                df[df["cluster"] == i]["clase"].value_counts(normalize=True) * 100
            ).head(3).items()
        )
        for i in tabla.index
    ]
    tabla["agentes_top"] = [
        ", ".join(
            f"{a} ({v}%)"
            for a, v in (
                df[df["cluster"] == i]
                .groupby("agente")["total_mwh"].sum()
                .div(df[df["cluster"] == i]["total_mwh"].sum())
                .mul(100)
                .sort_values(ascending=False)
                .head(3)
                .items()
            )
        )
        for i in tabla.index
    ]
    tabla.to_csv(C.TABLES_DIR / "final_perfil_clusters.csv", encoding="utf-8-sig")

    # Pruebas estadisticas por descriptor
    filas = []
    for col in DESCRIPTORES_CLUSTER:
        grupos = [
            df.loc[df["cluster"] == c, col].dropna().values
            for c in sorted(labels.unique())
        ]
        grupos = [g for g in grupos if len(g) > 0]
        try:
            H, p = kruskal(*grupos)
            eps = max(0.0, (H - len(grupos) + 1) / (len(df) - len(grupos)))
        except Exception:
            H, p, eps = np.nan, np.nan, np.nan
        filas.append({"descriptor": col, "H": H, "p": p, "epsilon2": eps})
    tests = pd.DataFrame(filas)
    tests["q_fdr"] = bh_fdr(tests["p"].fillna(1).tolist())
    tests["significativo"] = tests["q_fdr"] < 0.05
    tests.sort_values("epsilon2", ascending=False).to_csv(
        C.TABLES_DIR / "final_tests_descriptores.csv", index=False, encoding="utf-8-sig"
    )

    # Clase x cluster
    v, pv, tabla_clase = cramers_v(labels, df["clase"])
    tabla_clase.to_csv(C.TABLES_DIR / "final_clase_x_cluster.csv", encoding="utf-8-sig")

    # Robustez: quitar el efecto medio de la clase y re-clusterizar
    X_adj = X.copy()
    clases = df["clase"].reindex(X_adj.index)
    for clase in clases.unique():
        idx = clases[clases == clase].index
        X_adj.loc[idx] = X_adj.loc[idx] - X_adj.loc[idx].mean(axis=0)
    labels_adj, _ = ajustar(X_adj.to_numpy(dtype=float), algo, k)
    labels_adj = pd.Series(labels_adj, index=X.index, name="cluster_ajustado")
    ari_ajuste = adjusted_rand_score(labels, labels_adj)
    v_adj, pv_adj, _ = cramers_v(labels_adj, clases)

    # Estabilidad final (100 submuestras)
    media_est, std_est = estabilidad_submuestreo(
        X.to_numpy(dtype=float), algo, k, labels.to_numpy(), n_rep=100
    )
    aris = []
    rng = np.random.default_rng(C.RANDOM_STATE)
    n = len(labels)
    for r in range(100):
        idx = rng.permutation(n)
        ntr = int(0.8 * n)
        tr, te = idx[:ntr], idx[ntr:]
        lab_tr, _ = ajustar(X.to_numpy(dtype=float)[tr], algo, k, seed=C.RANDOM_STATE + r)
        cent, cls = centroides(X.to_numpy(dtype=float)[tr], lab_tr)
        lab_te = asignar_centroide(X.to_numpy(dtype=float)[te], cent, cls)
        aris.append(adjusted_rand_score(labels.to_numpy()[te], lab_te))
    aris = np.array(aris)

    # Exposicion por distribuidora
    expo_df = meta.loc[labels.index].copy()
    expo_df["cluster"] = labels
    total_agente = expo_df.groupby("agente")["total_mwh"].sum()
    shares = (
        expo_df.pivot_table(index="agente", columns="cluster", values="total_mwh",
                            aggfunc="sum", fill_value=0)
        .div(total_agente, axis=0)
    )
    expo = pd.DataFrame(index=shares.index)
    expo["total_mwh"] = total_agente
    expo["cluster_dominante"] = shares.idxmax(axis=1)
    expo["share_cluster_dominante"] = shares.max(axis=1)
    for c in shares.columns:
        expo[f"share_C{c}"] = shares[c]
    for col in ["cv", "tendencia_pct_mes", "amplitud_estacional", "crecimiento_12m"]:
        vals = desc.loc[labels.index, col]
        expo[f"{col}_ponderado"] = (
            (vals * expo_df["total_mwh"]).groupby(expo_df["agente"]).sum()
            / total_agente
        )
    expo = expo.rename(
        columns={
            "cv_ponderado": "cv_ponderado",
            "tendencia_pct_mes_ponderado": "tendencia_ponderada",
            "amplitud_estacional_ponderado": "amplitud_ponderada",
            "crecimiento_12m_ponderado": "crecimiento_ponderado",
        }
    )
    med_t = expo["tendencia_ponderada"].median()
    med_cv = expo["cv_ponderado"].median()
    expo["cuadrante"] = np.select(
        [
            (expo["tendencia_ponderada"] >= med_t) & (expo["cv_ponderado"] >= med_cv),
            (expo["tendencia_ponderada"] >= med_t) & (expo["cv_ponderado"] < med_cv),
            (expo["tendencia_ponderada"] < med_t) & (expo["cv_ponderado"] >= med_cv),
        ],
        ["Crecimiento-volatil", "Crecimiento-estable", "Contraccion-volatil"],
        default="Contraccion-estable",
    )
    expo["cluster_nombre"] = expo["cluster_dominante"].map(nombres)
    expo.sort_values("total_mwh", ascending=False).to_csv(
        C.TABLES_DIR / "final_exposicion_distribuidoras.csv", encoding="utf-8-sig"
    )

    # Etiquetas y artefactos
    out = pd.DataFrame(
        {
            "unidad": labels.index,
            "agente": df["agente"].reindex(labels.index),
            "clase": df["clase"].reindex(labels.index),
            "cluster": labels.values,
            "cluster_nombre": labels.map(nombres).values,
        }
    ).reset_index(drop=True)
    out = out.merge(desc[DESCRIPTORES_CLUSTER + ["total_mwh", "consumidores_medios"]],
                    left_on="unidad", right_index=True, how="left")
    out = out.merge(pca[["PC1", "PC2", "PC3"]], left_on="unidad", right_index=True, how="left")
    out.to_csv(C.TABLES_DIR / "final_labels.csv", index=False, encoding="utf-8-sig")

    # Representantes (mas cercanos al centroide en el espacio de clustering)
    Xdf = X.copy()
    reps = []
    for c in sorted(labels.unique()):
        idx = labels[labels == c].index
        cent = Xdf.loc[idx].mean(axis=0).to_numpy()
        d = ((Xdf.loc[idx].to_numpy() - cent) ** 2).sum(axis=1)
        for u in idx[np.argsort(d)[:3]]:
            reps.append({"cluster": c, "nombre": nombres[c], "unidad": u})
    pd.DataFrame(reps).to_csv(
        C.TABLES_DIR / "final_representantes.csv", index=False, encoding="utf-8-sig"
    )

    # Resumen JSON
    resumen = {
        "run_key": run_key,
        "representacion": rep,
        "escalado": esc,
        "algoritmo": algo,
        "k": k,
        "n_unidades": int(len(labels)),
        "n_agentes": int(df["agente"].nunique()),
        "silhouette_espacio": float(silhouette_score(X, labels)),
        "inercia": float(inercia),
        "estabilidad_100": float(media_est),
        "estabilidad_std_100": float(std_est),
        "ari_ajuste_por_clase": float(ari_ajuste),
        "cramers_v_clase": float(v),
        "p_clase": float(pv),
        "cramers_v_clase_ajustado": float(v_adj),
        "p_clase_ajustado": float(pv_adj),
        "nombres": {str(c): n for c, n in nombres.items()},
        "clusters": perfil.reset_index().to_dict(orient="records"),
    }
    with open(C.TABLES_DIR / "final_resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=float)

    # Modelo serializable
    joblib.dump(
        {
            "run_key": run_key,
            "representacion": rep,
            "escalado": esc,
            "algoritmo": algo,
            "k": k,
            "labels": labels,
            "nombres": nombres,
            "unidades": list(labels.index),
        },
        C.MODELS_DIR / "modelo_final.joblib",
    )

    # Figuras
    fig_cobertura()
    fig_unidades(meta, labels)
    fig_doe(res, run_key)
    fig_curva_k(res, run_key)
    fig_silueta(X.to_numpy(dtype=float), labels.to_numpy(), nombres)
    fig_pca(labels, nombres, pca)
    fig_centroides(serie, labels, nombres)
    fig_descriptores(df, labels, nombres)
    fig_clases(labels, meta, nombres)
    fig_exposicion(expo, labels, nombres)
    fig_estabilidad(aris, float(np.mean(aris)))

    # Export para Orange
    orange = out.copy()
    est = pd.read_csv(C.PROCESSED_DIR / "matriz_estacional12_mwh.csv", index_col=0)
    orange = orange.merge(est.add_prefix("est_"), left_on="unidad",
                          right_index=True, how="left")
    orange.to_csv(C.ORANGE_DIR / "aneel_orange.csv", index=False, encoding="utf-8-sig")
    serie_out = serie.copy()
    serie_out.insert(0, "cluster", labels.reindex(serie_out.index).values)
    serie_out.insert(0, "clase", df["clase"].reindex(serie_out.index).values)
    serie_out.insert(0, "agente", df["agente"].reindex(serie_out.index).values)
    serie_out.insert(0, "unidad", serie_out.index)
    serie_out.reset_index(drop=True).to_csv(
        C.ORANGE_DIR / "aneel_orange_serie68.csv", index=False, encoding="utf-8-sig"
    )
    # Version normalizada (winsor + z por fila): permite replicar el modelo final
    # en Orange con File -> k-Means, sin depender de normalizacion por columna.
    serie_z = X.copy()
    serie_z.insert(0, "cluster_nombre", labels.reindex(serie_z.index).map(nombres).values)
    serie_z.insert(0, "cluster", labels.reindex(serie_z.index).values)
    serie_z.insert(0, "clase", df["clase"].reindex(serie_z.index).values)
    serie_z.insert(0, "agente", df["agente"].reindex(serie_z.index).values)
    serie_z.insert(0, "unidad", serie_z.index)
    serie_z.reset_index(drop=True).to_csv(
        C.ORANGE_DIR / "aneel_orange_serie68_z.csv", index=False, encoding="utf-8-sig"
    )

    print(
        f"[final] k={k} | sil={resumen['silhouette_espacio']:.4f} | "
        f"estab100={media_est:.3f} | ARI ajuste clase={ari_ajuste:.3f} | "
        f"Cramer V={v:.3f}"
    )
    print(tabla[["nombre", "n_unidades", "share_mwh", "cv", "tendencia_pct_mes",
                 "amplitud_estacional", "crecimiento_12m"]].to_string())
    return resumen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-key", default=None)
    ap.add_argument("--auto", action="store_true")
    args = ap.parse_args()
    ejecutar(run_key=args.run_key, auto=True)


if __name__ == "__main__":
    main()
