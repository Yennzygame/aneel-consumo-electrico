"""Pipeline de datos ANEEL/SAMP: ingestion, limpieza, panel y features.

Uso:
    python -m src.aneel_pipeline --step panel
    python -m src.aneel_pipeline --step matrices
    python -m src.aneel_pipeline --step features
    python -m src.aneel_pipeline --step all

Decisiones metodologicas clave
------------------------------
1. VlrMercado NO es una variable unica: su unidad depende de DscDetalheMercado.
   Para consumo se usa exclusivamente "Energia TUSD (kWh)". "Energia TE (kWh)"
   es identica y sumarla duplicaria el consumo. Las filas de R$, kW, % y
   numero de consumidores se excluyen.
2. Se usa el mercado Regular y CATIVO (mercado cativo regulado). Se excluyen
   refacturacion, GD, sistema aislado/individual y RTE.
3. La unidad de analisis es el segmento de mercado:
       unidad = SigAgenteDistribuidora | DscClasseConsumoMercado
   No es un consumidor individual; es el agregado mensual que ANEEL publica
   y sobre el cual puede tomar decisiones regulatorias.
4. 2026-09 se excluye porque esta parcializado en el corte de datos.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from src import config as C

RAW_USE = [
    "DatCompetencia",
    "VlrMercado",
    "NomTipoMercado",
    "DscOpcaoEnergia",
    "DscDetalheMercado",
    "DscClasseConsumoMercado",
    "SigAgenteDistribuidora",
]

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def parse_br(series: pd.Series) -> pd.Series:
    """Convierte numeros en formato brasileño ('1.234,56') a float."""
    s = series.astype(str).str.strip()
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma, s.str.replace(".", "", regex=False))
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _limpiar_texto(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def _mes_iso(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M").astype(str)


# ---------------------------------------------------------------------------
# Etapa 1: panel largo (unidad x mes)
# ---------------------------------------------------------------------------


def construir_panel(force: bool = False) -> pd.DataFrame:
    out = C.PROCESSED_DIR / "painel_mensal.csv"
    if out.exists() and not force:
        print(f"[panel] ya existe: {out}")
        return pd.read_csv(out)

    t0 = time.time()
    archivos = sorted(C.RAW_DIR.glob("samp-*.csv"))
    if not archivos:
        raise FileNotFoundError(f"No hay CSV en {C.RAW_DIR}")

    energia_partes: list[pd.DataFrame] = []
    consumidores_partes: list[pd.DataFrame] = []
    filas_leidas = 0
    filas_regular_cativo = 0
    filas_energia = 0
    filas_consumidores = 0
    energia_negativa = 0

    for path in archivos:
        print(f"[panel] leyendo {path.name} ...", flush=True)
        for chunk in pd.read_csv(
            path,
            sep=";",
            encoding="latin1",
            usecols=RAW_USE,
            chunksize=400_000,
            dtype=str,
            low_memory=False,
        ):
            filas_leidas += len(chunk)
            chunk["NomTipoMercado"] = _limpiar_texto(chunk["NomTipoMercado"])
            chunk["DscOpcaoEnergia"] = _limpiar_texto(chunk["DscOpcaoEnergia"]).str.upper()
            chunk["DscDetalheMercado"] = _limpiar_texto(chunk["DscDetalheMercado"])
            chunk["DscClasseConsumoMercado"] = _limpiar_texto(
                chunk["DscClasseConsumoMercado"]
            ).replace(C.MAPA_CLASES)
            chunk["SigAgenteDistribuidora"] = _limpiar_texto(
                chunk["SigAgenteDistribuidora"]
            )
            chunk["mes"] = _mes_iso(chunk["DatCompetencia"])

            base = chunk[
                (chunk["NomTipoMercado"] == C.TIPO_MERCADO)
                & (chunk["DscOpcaoEnergia"] == C.OPCION_ENERGIA)
            ].copy()
            filas_regular_cativo += len(base)
            if base.empty:
                continue

            base["valor"] = parse_br(base["VlrMercado"])

            en = base[base["DscDetalheMercado"] == C.DETALLE_ENERGIA]
            if not en.empty:
                filas_energia += len(en)
                energia_negativa += int((en["valor"] < 0).sum())
                en = (
                    en.groupby(
                        ["SigAgenteDistribuidora", "DscClasseConsumoMercado", "mes"],
                        as_index=False,
                        sort=False,
                    )["valor"]
                    .sum(min_count=1)
                    .rename(columns={"valor": "consumo_kwh"})
                )
                energia_partes.append(en)

            co = base[base["DscDetalheMercado"] == C.DETALLE_CONSUMIDORES]
            if not co.empty:
                filas_consumidores += len(co)
                co = (
                    co.groupby(
                        ["SigAgenteDistribuidora", "DscClasseConsumoMercado", "mes"],
                        as_index=False,
                        sort=False,
                    )["valor"]
                    .sum(min_count=1)
                    .rename(columns={"valor": "n_consumidores"})
                )
                consumidores_partes.append(co)

    energia = (
        pd.concat(energia_partes, ignore_index=True)
        .groupby(
            ["SigAgenteDistribuidora", "DscClasseConsumoMercado", "mes"],
            as_index=False,
            sort=False,
        )["consumo_kwh"]
        .sum(min_count=1)
    )
    consumidores = (
        pd.concat(consumidores_partes, ignore_index=True)
        .groupby(
            ["SigAgenteDistribuidora", "DscClasseConsumoMercado", "mes"],
            as_index=False,
            sort=False,
        )["n_consumidores"]
        .sum(min_count=1)
    )

    panel = energia.merge(
        consumidores,
        on=["SigAgenteDistribuidora", "DscClasseConsumoMercado", "mes"],
        how="outer",
        validate="one_to_one",
    )
    panel["consumo_mwh"] = panel["consumo_kwh"] / 1000.0
    panel = panel.drop(columns=["consumo_kwh"])
    panel["unidad"] = (
        panel["SigAgenteDistribuidora"] + " | " + panel["DscClasseConsumoMercado"]
    )
    panel = panel.rename(
        columns={
            "SigAgenteDistribuidora": "agente",
            "DscClasseConsumoMercado": "clase",
        }
    )
    panel = panel[
        ["unidad", "agente", "clase", "mes", "consumo_mwh", "n_consumidores"]
    ].sort_values(["agente", "clase", "mes"])

    panel.to_csv(out, index=False, encoding="utf-8-sig")

    meta = {
        "archivos": [p.name for p in archivos],
        "filas_leidas": filas_leidas,
        "filas_regular_cativo": filas_regular_cativo,
        "filas_energia_tusd": filas_energia,
        "filas_num_consumidores": filas_consumidores,
        "filas_negativas_energia": energia_negativa,
        "filas_panel": int(len(panel)),
        "unidades": int(panel["unidad"].nunique()),
        "agentes": int(panel["agente"].nunique()),
        "mes_inicio": panel["mes"].min(),
        "mes_fin": panel["mes"].max(),
        "total_mwh": float(panel["consumo_mwh"].sum()),
        "total_consumidores_promedio_mes": float(
            panel.groupby("mes")["n_consumidores"].sum().mean()
        ),
        "segundos": round(time.time() - t0, 1),
    }
    with open(C.PROCESSED_DIR / "calidad_panel.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

    print(
        f"[panel] listo: {len(panel):,} filas | {panel['unidad'].nunique():,} unidades | "
        f"{meta['mes_inicio']}..{meta['mes_fin']} | {meta['total_mwh']/1e6:,.1f} TWh"
    )
    return panel


# ---------------------------------------------------------------------------
# Etapa 2: matrices unidad x mes
# ---------------------------------------------------------------------------


def construir_matrices(force: bool = False, cobertura_min: float = 0.95) -> pd.DataFrame:
    out = C.PROCESSED_DIR / "matriz_serie68_mwh.csv"
    if out.exists() and not force:
        print(f"[matrices] ya existe: {out}")
        return pd.read_csv(out, index_col=0)

    panel = construir_panel()
    panel = panel[panel["clase"].isin(C.CLASES)].copy()
    panel = panel[(panel["mes"] >= C.MES_INICIO) & (panel["mes"] <= C.MES_FIN)]

    energia = panel.pivot_table(
        index="unidad",
        columns="mes",
        values="consumo_mwh",
        aggfunc="sum",
        fill_value=np.nan,
        dropna=False,
    ).reindex(columns=C.MESES_STR)
    consumidores = panel.pivot_table(
        index="unidad",
        columns="mes",
        values="n_consumidores",
        aggfunc="sum",
        fill_value=np.nan,
        dropna=False,
    ).reindex(columns=C.MESES_STR)

    # Metadatos y cobertura
    meta = pd.DataFrame(index=energia.index)
    meta["agente"] = [u.split(" | ", 1)[0] for u in meta.index]
    meta["clase"] = [u.split(" | ", 1)[1] for u in meta.index]
    meta["meses_observados"] = energia.notna().sum(axis=1)
    meta["cobertura"] = meta["meses_observados"] / C.N_MESES
    meta["total_mwh"] = energia.sum(axis=1, min_count=1)
    meta["media_mwh"] = energia.mean(axis=1)
    meta["std_mwh"] = energia.std(axis=1)
    meta["cv"] = meta["std_mwh"] / meta["media_mwh"]
    meta["consumidores_medios"] = consumidores.mean(axis=1)
    meta["consumo_por_consumidor_mwh"] = (
        meta["total_mwh"] / (meta["consumidores_medios"] * meta["meses_observados"])
    )
    meta["mes_primero"] = energia.apply(
        lambda r: r.first_valid_index(), axis=1
    )
    meta["mes_ultimo"] = energia.apply(lambda r: r.last_valid_index(), axis=1)
    meta["incluida"] = meta["cobertura"] >= cobertura_min
    meta["motivo_exclusion"] = np.where(
        meta["incluida"], "", "cobertura temporal insuficiente"
    )
    meta.loc[meta["total_mwh"].fillna(0) <= 0, "incluida"] = False
    meta.loc[
        meta["total_mwh"].fillna(0) <= 0, "motivo_exclusion"
    ] = "consumo total nulo"

    # Interpolacion solo para huecos internos pequenos; si quedan NaN se excluye.
    energia_interp = energia.interpolate(
        method="linear", axis=1, limit=2, limit_direction="both"
    )
    consumidores_interp = consumidores.interpolate(
        method="linear", axis=1, limit=2, limit_direction="both"
    )
    quedan_nan = energia_interp.isna().any(axis=1)
    meta.loc[quedan_nan & meta["incluida"], "incluida"] = False
    meta.loc[
        quedan_nan & (meta["motivo_exclusion"] == ""), "motivo_exclusion"
    ] = "huecos temporales no imputables"

    seleccion = meta.index[meta["incluida"]]
    matriz = energia_interp.loc[seleccion].copy()
    matriz_consumidores = consumidores_interp.loc[seleccion].copy()

    matriz.to_csv(out, encoding="utf-8-sig")
    matriz_consumidores.to_csv(
        C.PROCESSED_DIR / "matriz_consumidores.csv", encoding="utf-8-sig"
    )
    meta.to_csv(C.PROCESSED_DIR / "unidades_meta.csv", encoding="utf-8-sig")
    meta[~meta["incluida"]].to_csv(
        C.PROCESSED_DIR / "unidades_excluidas.csv", encoding="utf-8-sig"
    )

    print(
        f"[matrices] unidades totais={len(meta):,} | incluidas={len(matriz):,} | "
        f"excluidas={len(meta)-len(matriz):,} | matriz={matriz.shape}"
    )
    print(
        f"[matrices] consumo incluido={matriz.sum().sum()/1e6:,.1f} TWh "
        f"({matriz.sum().sum()/panel['consumo_mwh'].sum()*100:,.1f}% del panel filtrado)"
    )
    return matriz


# ---------------------------------------------------------------------------
# Etapa 3: features
# ---------------------------------------------------------------------------


def _descriptores_serie(y: np.ndarray, meses: np.ndarray) -> dict:
    """Descriptores de forma, tendencia y estacionalidad de una serie mensual."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    x = np.arange(n)
    media = float(np.mean(y))
    sd = float(np.std(y))
    cv = sd / media if media > 0 else 0.0

    if n > 2 and np.std(x) > 0 and sd > 0:
        beta = float(np.cov(x, y, ddof=0)[0, 1] / np.var(x))
        corr = float(np.corrcoef(x, y)[0, 1])
        r2 = corr**2
    else:
        beta, r2 = 0.0, 0.0
    tendencia_pct = beta / media * 100 if media > 0 else 0.0

    estacional = np.array([y[meses == m].mean() for m in range(1, 13)])
    amp = (estacional.max() - estacional.min()) / media if media > 0 else 0.0
    var_y = np.var(y)
    fuerza = np.var(estacional[meses - 1]) / var_y if var_y > 0 else 0.0

    def _corr(a: np.ndarray, b: np.ndarray) -> float:
        if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])

    ac1 = _corr(y[:-1], y[1:])
    ac12 = _corr(y[:-12], y[12:]) if n > 12 else 0.0

    if n > 12 and np.all(y[:-12] > 0):
        yoy = y[12:] / y[:-12] - 1
        yoy_media = float(np.mean(yoy))
        yoy_std = float(np.std(yoy))
    else:
        yoy_media, yoy_std = 0.0, 0.0

    pico = int(np.argmax(estacional)) + 1
    valle = int(np.argmin(estacional)) + 1
    cummax = np.maximum.accumulate(y)
    drawdown = float(np.max(1 - y / cummax)) if np.all(cummax > 0) else 0.0

    p10, p90 = np.percentile(y, [10, 90])
    rango_p90_p10 = float((p90 - p10) / media) if media > 0 else 0.0
    iqr = float((np.percentile(y, 75) - np.percentile(y, 25)) / media) if media > 0 else 0.0

    crecimiento = (
        float(y[-12:].mean() / y[:12].mean() - 1) if y[:12].mean() > 0 else 0.0
    )
    share_bajo = float(np.mean(y < 0.8 * media)) if media > 0 else 0.0
    share_alto = float(np.mean(y > 1.2 * media)) if media > 0 else 0.0

    return {
        "cv": cv,
        "tendencia_pct_mes": tendencia_pct,
        "tendencia_r2": r2,
        "amplitud_estacional": amp,
        "fuerza_estacionalidad": fuerza,
        "ac1": ac1,
        "ac12": ac12,
        "yoy_media": yoy_media,
        "yoy_std": yoy_std,
        "drawdown_max": drawdown,
        "rango_p90_p10": rango_p90_p10,
        "iqr_relativo": iqr,
        "share_bajo_80": share_bajo,
        "share_alto_120": share_alto,
        "crecimiento_12m": crecimiento,
        "mes_pico": pico,
        "mes_valle": valle,
        "pico_sin": float(np.sin(2 * np.pi * (pico - 1) / 12)),
        "pico_cos": float(np.cos(2 * np.pi * (pico - 1) / 12)),
        "valle_sin": float(np.sin(2 * np.pi * (valle - 1) / 12)),
        "valle_cos": float(np.cos(2 * np.pi * (valle - 1) / 12)),
    }


DESCRIPTORES_CLUSTER = [
    "cv",
    "tendencia_pct_mes",
    "tendencia_r2",
    "amplitud_estacional",
    "fuerza_estacionalidad",
    "ac1",
    "ac12",
    "yoy_media",
    "yoy_std",
    "drawdown_max",
    "rango_p90_p10",
    "iqr_relativo",
    "share_bajo_80",
    "share_alto_120",
    "crecimiento_12m",
    "pico_sin",
    "pico_cos",
    "valle_sin",
    "valle_cos",
]


def construir_features(force: bool = False) -> dict[str, pd.DataFrame]:
    matrices_existen = (
        (C.PROCESSED_DIR / "matriz_serie68_mwh.csv").exists()
        and (C.PROCESSED_DIR / "matriz_estacional12_mwh.csv").exists()
        and (C.PROCESSED_DIR / "descriptores.csv").exists()
        and (C.PROCESSED_DIR / "pca_serie68.csv").exists()
    )
    if matrices_existen and not force:
        print("[features] ya existen; se cargan")
        serie = pd.read_csv(
            C.PROCESSED_DIR / "matriz_serie68_mwh.csv", index_col=0
        )
        est = pd.read_csv(
            C.PROCESSED_DIR / "matriz_estacional12_mwh.csv", index_col=0
        )
        desc = pd.read_csv(C.PROCESSED_DIR / "descriptores.csv", index_col=0)
        pca = pd.read_csv(C.PROCESSED_DIR / "pca_serie68.csv", index_col=0)
        return {"serie68": serie, "estacional12": est, "descriptores": desc, "pca": pca}

    serie = construir_matrices()
    serie.columns = [str(c) for c in serie.columns]
    periodos = pd.PeriodIndex(serie.columns, freq="M")
    meses = periodos.month.to_numpy()

    # Perfil estacional: promedio de cada mes calendario (12 features)
    tmp = serie.T.copy()
    tmp.index = periodos
    estacional = tmp.groupby(tmp.index.month).mean().T
    estacional.columns = [f"M{m:02d}" for m in estacional.columns]

    # Descriptores de forma
    filas = []
    for unidad, row in serie.iterrows():
        d = _descriptores_serie(row.to_numpy(dtype=float), meses)
        d["unidad"] = unidad
        filas.append(d)
    descriptores = pd.DataFrame(filas).set_index("unidad")

    # Metadatos de tamano (para interpretacion, no para clustering de forma)
    meta = pd.read_csv(C.PROCESSED_DIR / "unidades_meta.csv", index_col=0)
    descriptores["total_mwh"] = meta.loc[descriptores.index, "total_mwh"]
    descriptores["log_total_mwh"] = np.log1p(descriptores["total_mwh"])
    descriptores["consumidores_medios"] = meta.loc[
        descriptores.index, "consumidores_medios"
    ]
    descriptores["log_consumidores"] = np.log1p(
        descriptores["consumidores_medios"].fillna(0)
    )
    descriptores["mwh_por_consumidor"] = meta.loc[
        descriptores.index, "consumo_por_consumidor_mwh"
    ]
    descriptores["agente"] = meta.loc[descriptores.index, "agente"]
    descriptores["clase"] = meta.loc[descriptores.index, "clase"]

    # PCA sobre la forma (serie estandarizada por fila)
    serie_z = row_zscore(serie)
    pca_model = PCA(n_components=10, random_state=C.RANDOM_STATE)
    scores = pca_model.fit_transform(serie_z)
    pca = pd.DataFrame(
        scores, index=serie.index, columns=[f"PC{i+1}" for i in range(scores.shape[1])]
    )
    var = pd.DataFrame(
        {
            "componente": [f"PC{i+1}" for i in range(len(pca_model.explained_variance_ratio_))],
            "varianza_explicada": pca_model.explained_variance_ratio_,
            "acumulada": np.cumsum(pca_model.explained_variance_ratio_),
        }
    )

    serie.to_csv(C.PROCESSED_DIR / "matriz_serie68_mwh.csv", encoding="utf-8-sig")
    estacional.to_csv(
        C.PROCESSED_DIR / "matriz_estacional12_mwh.csv", encoding="utf-8-sig"
    )
    descriptores.to_csv(C.PROCESSED_DIR / "descriptores.csv", encoding="utf-8-sig")
    pca.to_csv(C.PROCESSED_DIR / "pca_serie68.csv", encoding="utf-8-sig")
    var.to_csv(C.PROCESSED_DIR / "pca_varianza.csv", index=False, encoding="utf-8-sig")

    print(f"[features] serie68={serie.shape} | estacional12={estacional.shape} | "
          f"descriptores={descriptores.shape} | PCA acumulado(3)="
          f"{var['acumulada'].iloc[2]:.3f}")

    return {
        "serie68": serie,
        "estacional12": estacional,
        "descriptores": descriptores,
        "pca": pca,
    }


# ---------------------------------------------------------------------------
# Normalizaciones
# ---------------------------------------------------------------------------


def row_zscore(df: pd.DataFrame) -> pd.DataFrame:
    mu = df.mean(axis=1)
    sd = df.std(axis=1, ddof=0).replace(0, np.nan)
    return df.sub(mu, axis=0).div(sd, axis=0).fillna(0.0)


def log_row_zscore(df: pd.DataFrame) -> pd.DataFrame:
    return row_zscore(np.log1p(df.clip(lower=0)))


def row_minmax(df: pd.DataFrame) -> pd.DataFrame:
    mn = df.min(axis=1)
    mx = df.max(axis=1)
    rng = (mx - mn).replace(0, np.nan)
    return df.sub(mn, axis=0).div(rng, axis=0).fillna(0.0)


def col_zscore(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        StandardScaler().fit_transform(df),
        index=df.index,
        columns=df.columns,
    )


def col_robust(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        RobustScaler().fit_transform(df),
        index=df.index,
        columns=df.columns,
    )


def col_minmax(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        MinMaxScaler().fit_transform(df),
        index=df.index,
        columns=df.columns,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step",
        choices=["panel", "matrices", "features", "all"],
        default="all",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.step in ("panel", "all"):
        construir_panel(force=args.force)
    if args.step in ("matrices", "all"):
        construir_matrices(force=args.force)
    if args.step in ("features", "all"):
        construir_features(force=args.force)


if __name__ == "__main__":
    main()
