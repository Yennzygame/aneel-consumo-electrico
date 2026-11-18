"""Evolucion del mercado cativo vs libre vs generacion distribuida (GD).

Sirve para interpretar el cluster de contraccion: si el mercado cativo cae
mientras el libre y la GD crecen, la contraccion es consistente con migracion
de consumidores, no con un error de datos.

Salida: reports/tables/mercado_evolucion.csv
        reports/figures/13_mercado_cativo_livre_gd.png
"""
from __future__ import annotations

import glob
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import config as C

USE = ["DatCompetencia", "VlrMercado", "NomTipoMercado", "DscOpcaoEnergia",
       "DscDetalheMercado"]


def parse_br(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma, s.str.replace(".", "", regex=False))
    return pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")


def main() -> None:
    acc = defaultdict(float)
    for path in sorted(glob.glob(str(C.RAW_DIR / "samp-*.csv"))):
        print("leyendo", path.split("\\")[-1], flush=True)
        for ch in pd.read_csv(path, sep=";", encoding="latin1", usecols=USE,
                              chunksize=400_000, dtype=str, low_memory=False):
            ch["mes"] = pd.to_datetime(ch["DatCompetencia"], errors="coerce").dt.to_period("M").astype(str)
            ch["val"] = parse_br(ch["VlrMercado"])
            ch["tipo"] = ch["NomTipoMercado"].astype(str).str.strip()
            ch["op"] = ch["DscOpcaoEnergia"].astype(str).str.strip().str.upper()
            ch["det"] = ch["DscDetalheMercado"].astype(str).str.strip()

            reg = ch[(ch["tipo"] == "Regular") & (ch["det"] == "Energia TUSD (kWh)")]
            for (mes, op), g in reg.groupby(["mes", "op"]):
                acc[(mes, f"Regular {op}")] += float(g["val"].sum())

            gd = ch[
                ch["tipo"].str.startswith("Sistema de Compensação")
                & ~ch["tipo"].str.contains("Refaturamento", na=False)
                & ch["det"].isin(["Energia Injetada (kWh)", "Energia Consumida (kWh)"])
            ]
            for (mes, det), g in gd.groupby(["mes", "det"]):
                acc[(mes, f"GD {det}")] += float(g["val"].sum())

    filas = [{"mes": m, "serie": s, "gwh": v / 1e6} for (m, s), v in acc.items()]
    df = pd.DataFrame(filas)
    df = df[(df["mes"] >= C.MES_INICIO) & (df["mes"] <= C.MES_FIN)]
    piv = df.pivot(index="mes", columns="serie", values="gwh").sort_index()
    piv.to_csv(C.TABLES_DIR / "mercado_evolucion.csv", encoding="utf-8-sig")

    # Comparacion 2021 vs ultimos 12 meses
    comp = []
    for col in piv.columns:
        ini = piv.loc["2021-01":"2021-12", col].mean()
        fin = piv.loc["2025-09":"2026-08", col].mean()
        comp.append({"serie": col, "prom_2021_gwh": ini, "prom_ult12_gwh": fin,
                     "variacion_pct": (fin / ini - 1) * 100 if ini else None})
    compdf = pd.DataFrame(comp).sort_values("variacion_pct", ascending=False)
    compdf.to_csv(C.TABLES_DIR / "mercado_variacion.csv", index=False, encoding="utf-8-sig")
    print(compdf.to_string(index=False))

    x = pd.PeriodIndex(piv.index, freq="M").to_timestamp()
    fig, ax = plt.subplots(figsize=(10, 4.6))
    series = {
        "Regular CATIVO": ("#E4572E", "Mercado cativo (objeto del estudio)"),
        "Regular LIVRE": ("#2E86AB", "Mercado libre"),
        "GD Energia Injetada (kWh)": ("#28A745", "GD - energia inyectada"),
        "GD Energia Consumida (kWh)": ("#6C5B7B", "GD - energia consumida"),
    }
    for col, (color, label) in series.items():
        if col in piv.columns:
            ax.plot(x, piv[col].values, lw=1.9, color=color, label=label)
    ax.set_title("Evolucion del mercado electrico: cativo, libre y generacion distribuida")
    ax.set_ylabel("GWh/mes")
    ax.set_xlabel("Mes de competencia")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.tick_params(axis="x", rotation=45)
    fig.savefig(C.FIGURES_DIR / "13_mercado_cativo_livre_gd.png", bbox_inches="tight", dpi=220)
    plt.close(fig)
    print("[fig] 13_mercado_cativo_livre_gd.png")


if __name__ == "__main__":
    main()
