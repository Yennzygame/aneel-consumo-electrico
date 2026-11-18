"""Figura didactica de la unidad de analisis.

Muestra, en una sola imagen:
  A. La matriz 700 filas x 68 meses, con una fila resaltada.
  B. Esa fila convertida en una serie de 68 puntos.
  C. Las 7 clases de una misma distribuidora: 7 filas -> 7 graficas.
  D. Las 700 series normalizadas y el promedio de cada arquetipo.

Uso:
    python -m tools.fig_unidad_analisis
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "reports" / "tables"
FIGURES = ROOT / "reports" / "figures"

AZUL = "#1f77b4"
ROJO = "#d62728"
VERDE = "#2ca02c"
COLORES = {0: ROJO, 1: AZUL, 2: VERDE}
NOMBRES = {0: "Contracción", 1: "Base estable", 2: "Crecimiento"}

DESTACADA = "CEMIG-D | Residencial"
DISTRIBUIDORA = "CEMIG-D"
ORDEN_CLASES = [
    "Residencial",
    "Comercial",
    "Industrial",
    "Rural",
    "Poder público",
    "Iluminação pública",
    "Serviço público",
]


def cargar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    serie = pd.read_csv(PROCESSED / "matriz_serie68_mwh.csv", index_col=0)
    serie.index.name = "unidad"
    serie.columns = [str(c) for c in serie.columns]
    labels = pd.read_csv(TABLES / "final_labels.csv").set_index("unidad")
    medias = serie.mean(axis=1)
    desv = serie.std(axis=1).replace(0, np.nan)
    z = serie.sub(medias, axis=0).div(desv, axis=0)
    return serie, labels, z


def main() -> None:
    serie, labels, z = cargar()
    meses = pd.PeriodIndex(serie.columns, freq="M").to_timestamp()

    # Filas del panel A: CEMIG-D completo + una unidad grande por arquetipo.
    filas = [
        "CEMIG-D | Residencial",
        "CEMIG-D | Poder público",
        "CEMIG-D | Comercial",
        "CEMIG-D | Industrial",
        "CEMIG-D | Rural",
        "CEMIG-D | Serviço público",
        "CEMIG-D | Iluminação pública",
        "ELETROPAULO | Industrial",
        "COPEL-DIS | Residencial",
        "COELBA | Comercial",
        "ENEL CE | Iluminação pública",
        "EQUATORIAL GO | Poder público",
    ]

    fig = plt.figure(figsize=(16.5, 15.0), constrained_layout=True)
    gs = GridSpec(
        5,
        4,
        figure=fig,
        height_ratios=[1.15, 1.15, 0.85, 0.85, 0.95],
        hspace=0.45,
        wspace=0.35,
    )

    # ------------------------------------------------------------------
    # A. Matriz: filas = unidades, columnas = meses
    # ------------------------------------------------------------------
    ax_a = fig.add_subplot(gs[0:2, 0:2])
    matriz = z.loc[filas]
    im = ax_a.imshow(
        matriz.values,
        aspect="auto",
        cmap="RdBu_r",
        vmin=-2.5,
        vmax=2.5,
        interpolation="nearest",
    )
    ax_a.add_patch(
        Rectangle((-0.5, -0.5), len(serie.columns), 1, fill=False, ec="black", lw=2.2)
    )
    ax_a.set_yticks(range(len(filas)))
    ax_a.set_yticklabels(filas, fontsize=7.5)
    años = [i for i, c in enumerate(serie.columns) if c.endswith("-01")]
    ax_a.set_xticks(años)
    ax_a.set_xticklabels([serie.columns[i][:4] for i in años], fontsize=8)
    ax_a.set_title(
        "A. La matriz: 700 filas × 68 meses\n(cada fila es una unidad; cada columna, un mes)",
        fontsize=11,
        loc="left",
    )
    ax_a.set_xlabel("mes")
    ax_a.set_ylabel("unidad = distribuidora | clase")
    fig.colorbar(im, ax=ax_a, fraction=0.035, pad=0.015, label="z (forma)")
    ax_a.annotate(
        "fila resaltada",
        xy=(66, 0),
        xytext=(50, 3.2),
        fontsize=8.5,
        arrowprops=dict(arrowstyle="->", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.6", alpha=0.9),
    )

    # ------------------------------------------------------------------
    # B. La fila resaltada, extraida como una sola serie de 68 puntos
    # ------------------------------------------------------------------
    ax_b = fig.add_subplot(gs[0:2, 2:4])
    y = serie.loc[DESTACADA] / 1000.0  # GWh
    ax_b.plot(meses, y.values, color="#111111", lw=1.4, marker="o", ms=2.6)
    ax_b.fill_between(meses, y.values, y.min() * 0.98, color=AZUL, alpha=0.12)
    ax_b.set_title(
        "B. Esa fila es UNA serie de 68 puntos\n(no son 68 gráficas: son 68 meses en una línea)",
        fontsize=11,
        loc="left",
    )
    ax_b.set_ylabel("GWh/mes")
    ax_b.grid(alpha=0.25)
    ax_b.set_ylim(y.min() * 0.94, y.max() * 1.22)
    ax_b.xaxis.set_major_locator(mdates.YearLocator())
    ax_b.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_b.annotate(
        f"{DESTACADA}\n{y.iloc[0]:,.0f} → {y.iloc[-1]:,.0f} GWh/mes",
        xy=(meses[1], y.iloc[1]),
        xytext=(meses[8], y.max() * 1.10),
        fontsize=8.5,
        arrowprops=dict(arrowstyle="->", lw=1.0),
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.6", alpha=0.95),
    )
    ax_b.text(
        0.02,
        0.04,
        "cada punto = un mes",
        transform=ax_b.transAxes,
        fontsize=8.5,
        color="#444444",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
    )

    # ------------------------------------------------------------------
    # C. Una distribuidora, siete clases: siete filas, siete gráficas
    # ------------------------------------------------------------------
    sub = serie.loc[[f"{DISTRIBUIDORA} | {c}" for c in ORDEN_CLASES]]
    for i, clase in enumerate(ORDEN_CLASES):
        ax = fig.add_subplot(gs[2, i]) if i < 4 else fig.add_subplot(gs[3, i - 4])
        unidad = f"{DISTRIBUIDORA} | {clase}"
        cluster = int(labels.loc[unidad, "cluster"])
        color = COLORES[cluster]
        ax.plot(meses, sub.loc[unidad].values / 1000.0, color=color, lw=1.3)
        if i == 0:
            titulo = (
                "C. Siete clases de CEMIG-D: 7 filas → 7 gráficas\n"
                f"{clase} — {NOMBRES[cluster]}"
            )
        else:
            titulo = f"{clase}\n{NOMBRES[cluster]}"
        ax.set_title(titulo, fontsize=8.5, color=color, loc="left")
        ax.grid(alpha=0.25)
        ax.tick_params(labelsize=7)
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        if i < 4:
            ax.tick_params(labelbottom=False)
        if i % 4 == 0:
            ax.set_ylabel("GWh/mes", fontsize=8)

    # Octavo hueco: leyenda de colores
    ax_ley = fig.add_subplot(gs[3, 3])
    ax_ley.axis("off")
    for k in [0, 1, 2]:
        ax_ley.plot([], [], color=COLORES[k], lw=2.5, label=NOMBRES[k])
    ax_ley.legend(loc="center left", frameon=False, fontsize=9, title="Arquetipo")
    ax_ley.text(
        0.0,
        0.95,
        "Cada clase de una misma\ndistribuidora es una fila\ny produce su propia línea.",
        transform=ax_ley.transAxes,
        fontsize=8.5,
        color="0.25",
        va="top",
    )

    # ------------------------------------------------------------------
    # D. Las 700 series normalizadas y el promedio de cada arquetipo
    # ------------------------------------------------------------------
    ax_d = fig.add_subplot(gs[4, :])
    for _, fila in z.iterrows():
        ax_d.plot(meses, fila.values, color="0.55", lw=0.45, alpha=0.08)
    for k in [0, 1, 2]:
        unidades = labels.index[labels["cluster"] == k]
        media = z.loc[unidades].mean(axis=0)
        ax_d.plot(meses, media.values, color=COLORES[k], lw=2.8, label=NOMBRES[k])
    ax_d.set_title(
        "D. Las 700 filas juntas: 700 series normalizadas (gris) y el promedio de cada arquetipo (color)",
        fontsize=11,
        loc="left",
    )
    ax_d.set_ylabel("z")
    ax_d.grid(alpha=0.2)
    ax_d.legend(ncol=3, fontsize=9, frameon=False, loc="upper left")
    ax_d.xaxis.set_major_locator(mdates.YearLocator())
    ax_d.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_d.set_xlim(meses[0], meses[-1])

    fig.suptitle(
        "Unidad de análisis: segmento distribuidora × clase de consumo → una serie mensual",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.005,
        0.002,
        "Fuente: ANEEL/SAMP, mercado Regular CATIVO, Energía TUSD (kWh), 2021-01 a 2026-08. "
        "A y D usan z por fila (forma); B y C usan GWh/mes (escala real).",
        fontsize=7.5,
        color="0.35",
    )

    FIGURES.mkdir(parents=True, exist_ok=True)
    salida = FIGURES / "00_unidad_analisis_series.png"
    fig.savefig(salida, dpi=190, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig] {salida}")


if __name__ == "__main__":
    main()
