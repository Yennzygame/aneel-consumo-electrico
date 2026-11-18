"""Verificacion de coherencia de los entregables del proyecto ANEEL / IND2622.

Comprueba que los artefactos existan, que las cifras clave coincidan entre si y
que los notebooks tengan salidas. No reentrena nada: solo audita lo generado.

Uso:
    python -m tools.verificar_entregables
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "reports" / "tables"
FIGURES = ROOT / "reports" / "figures"
ORANGE = ROOT / "reports" / "orange"
DOCS = ROOT / "docs"
NOTEBOOKS = ROOT / "notebooks"

fallos: list[str] = []
avisos: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  OK   {msg}")
    else:
        print(f"  FALLA {msg}")
        fallos.append(msg)


def warn(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  AVISO {msg}")
        avisos.append(msg)


def seccion(titulo: str) -> None:
    print(f"\n[{titulo}]")


# ---------------------------------------------------------------------------
# 1. Archivos esperados
# ---------------------------------------------------------------------------
seccion("Archivos")
esperados = [
    ROOT / "README.md",
    ROOT / "requirements.txt",
    ROOT / "run_all.ps1",
    ROOT / "mlflow.db",
    ROOT / "models" / "modelo_final.joblib",
    TABLES / "doe_resultados.csv",
    TABLES / "doe_ranking.csv",
    TABLES / "doe_top20.csv",
    TABLES / "final_resumen.json",
    TABLES / "final_labels.csv",
    TABLES / "final_perfil_clusters.csv",
    TABLES / "final_tests_descriptores.csv",
    TABLES / "final_exposicion_distribuidoras.csv",
    TABLES / "final_clase_x_cluster.csv",
    TABLES / "mercado_variacion.csv",
    TABLES / "orange_verificacion.json",
    ORANGE / "aneel_orange.csv",
    ORANGE / "aneel_orange_serie68.csv",
    ORANGE / "aneel_orange_serie68_z.csv",
]
for f in esperados:
    check(f.exists() and f.stat().st_size > 0, f"{f.relative_to(ROOT)} existe y no esta vacio")

docs = sorted(DOCS.glob("0*.md"))
check(len(docs) >= 8, f"documentacion presente ({len(docs)} documentos)")
for d in docs:
    check(d.stat().st_size > 3000, f"{d.name} tiene contenido (>3 KB)")

notebooks = sorted(NOTEBOOKS.glob("*.ipynb"))
check(len(notebooks) == 5, f"5 notebooks ({len(notebooks)} encontrados)")
for nb in notebooks:
    nbjson = json.loads(nb.read_text(encoding="utf-8"))
    celdas = nbjson.get("cells", [])
    con_salida = sum(
        1
        for c in celdas
        if c.get("cell_type") == "code" and c.get("outputs")
    )
    codigo = sum(1 for c in celdas if c.get("cell_type") == "code")
    check(
        con_salida >= max(1, codigo // 2),
        f"{nb.name}: {con_salida}/{codigo} celdas de codigo con salida",
    )

figuras = sorted(FIGURES.glob("*.png"))
check(len(figuras) == 13, f"13 figuras ({len(figuras)} encontradas)")
for fig in figuras:
    check(fig.stat().st_size > 20_000, f"{fig.name} > 20 KB ({fig.stat().st_size // 1024} KB)")

# ---------------------------------------------------------------------------
# 2. Diseno de experimentos
# ---------------------------------------------------------------------------
seccion("DoE")
doe = pd.read_csv(TABLES / "doe_resultados.csv")
check(len(doe) == 504, f"504 corridas ({len(doe)})")
check(doe["run_key"].nunique() == 504, f"504 run_key unicos ({doe['run_key'].nunique()})")
check(
    doe.groupby(["representacion", "escalado"]).ngroups == 18,
    f"18 pipelines representacion x escalado ({doe.groupby(['representacion','escalado']).ngroups})",
)
check(doe["algoritmo"].nunique() == 4, f"4 algoritmos ({sorted(doe['algoritmo'].unique())})")
check(sorted(doe["k"].unique()) == list(range(2, 9)), f"k = 2..8 ({sorted(doe['k'].unique())})")
check(doe["silhouette_ref"].notna().sum() == 504, "las 504 corridas tienen silhouette en espacio comun")
check(doe["estabilidad_media"].notna().sum() == 504, "las 504 corridas tienen estabilidad")

ranking = pd.read_csv(TABLES / "doe_ranking.csv")
check(len(ranking) == 68, f"68 candidatas tras filtros ({len(ranking)})")
check(
    ranking.iloc[0]["run_key"] == "serie68|winsor_z_fila|kmeans|k3",
    f"top del ranking = {ranking.iloc[0]['run_key']}",
)

# ---------------------------------------------------------------------------
# 3. Modelo final y arquetipos
# ---------------------------------------------------------------------------
seccion("Modelo final")
resumen = json.loads((TABLES / "final_resumen.json").read_text(encoding="utf-8"))
check(resumen["run_key"] == ranking.iloc[0]["run_key"], "modelo final = top del ranking")
check(resumen["n_unidades"] == 700, f"700 unidades ({resumen['n_unidades']})")
check(resumen["k"] == 3, f"k = 3 ({resumen['k']})")
check(abs(resumen["silhouette_espacio"] - 0.2635) < 1e-3, f"silhouette = {resumen['silhouette_espacio']:.4f}")
check(abs(resumen["estabilidad_100"] - 0.883) < 1e-3, f"estabilidad 100 = {resumen['estabilidad_100']:.4f}")
check(abs(resumen["cramers_v_clase"] - 0.568) < 1e-3, f"Cramer V = {resumen['cramers_v_clase']:.4f}")
check(abs(resumen["ari_ajuste_por_clase"] - 0.333) < 1e-3, f"ARI ajustado = {resumen['ari_ajuste_por_clase']:.4f}")

perfiles = pd.DataFrame(resumen["clusters"]).set_index("cluster")
check(perfiles["n_unidades"].sum() == 700, f"suma de unidades = {perfiles['n_unidades'].sum()}")
check(abs(perfiles["share_mwh"].sum() - 1.0) < 1e-9, f"shares suman {perfiles['share_mwh'].sum():.6f}")
total_twh = perfiles["total_mwh"].sum() / 1e6
check(abs(total_twh - 1587.2) < 1.0, f"consumo total = {total_twh:.1f} TWh")
check(
    dict(perfiles["n_unidades"].astype(int)) == {0: 366, 1: 187, 2: 147},
    f"tamanos = {dict(perfiles['n_unidades'].astype(int))}",
)

labels = pd.read_csv(TABLES / "final_labels.csv")
check(len(labels) == 700, f"final_labels: 700 filas ({len(labels)})")
check(labels["cluster"].nunique() == 3, "final_labels: 3 clusters")
check(
    labels["cluster"].value_counts().sort_index().to_dict() == {0: 366, 1: 187, 2: 147},
    f"conteos en labels = {labels['cluster'].value_counts().sort_index().to_dict()}",
)

tests = pd.read_csv(TABLES / "final_tests_descriptores.csv")
check(len(tests) == 19, f"19 descriptores testeados ({len(tests)})")
check(bool(tests["significativo"].all()), "todos significativos tras FDR")
check(abs(tests.iloc[0]["epsilon2"] - 0.721) < 1e-3, f"epsilon2 max = {tests.iloc[0]['epsilon2']:.3f}")

expo = pd.read_csv(TABLES / "final_exposicion_distribuidoras.csv")
check(len(expo) == 101, f"101 distribuidoras ({len(expo)})")

# ---------------------------------------------------------------------------
# 4. Mercado y Orange
# ---------------------------------------------------------------------------
seccion("Mercado")
mercado = pd.read_csv(TABLES / "mercado_variacion.csv")
cativo = mercado.loc[mercado["serie"] == "Regular CATIVO"].iloc[0]
libre = mercado.loc[mercado["serie"] == "Regular LIVRE"].iloc[0]
gd = mercado.loc[mercado["serie"].str.startswith("GD Energia Injetada")].iloc[0]
check(abs(cativo["variacion_pct"] + 12.8) < 0.1, f"CATIVO {cativo['variacion_pct']:.1f}%")
check(abs(libre["variacion_pct"] - 33.3) < 0.1, f"LIVRE {libre['variacion_pct']:.1f}%")
check(abs(gd["variacion_pct"] - 767.3) < 0.1, f"GD inyectada {gd['variacion_pct']:.1f}%")

seccion("Orange")
ov = json.loads((TABLES / "orange_verificacion.json").read_text(encoding="utf-8"))
check(abs(ov["replica_modelo_final"]["ari_vs_proyecto"] - 1.0) < 1e-9, "replica Orange ARI = 1,0")
check(
    {int(k): int(v) for k, v in ov["replica_modelo_final"]["tamanos"].items()} == {0: 366, 1: 187, 2: 147},
    f"tamanos Orange = {ov['replica_modelo_final']['tamanos']}",
)
check(
    abs(ov["replica_modelo_final"]["silhouette_orange"] - 0.2635) < 1e-4,
    "silhouette Orange = 0,2635",
)
z = pd.read_csv(ORANGE / "aneel_orange_serie68_z.csv")
check(len(z) == 700, f"export z: 700 filas ({len(z)})")
check(z.shape[1] == 73, f"export z: 73 columnas ({z.shape[1]})")
serie68 = pd.read_csv(ORANGE / "aneel_orange_serie68.csv")
check(len(serie68) == 700 and serie68.shape[1] == 72, f"export serie68: {serie68.shape}")

# ---------------------------------------------------------------------------
# 5. Coherencia de cifras en la documentacion
# ---------------------------------------------------------------------------
seccion("Documentacion")
cuerpo_docs = "\n".join(d.read_text(encoding="utf-8") for d in docs)
for aguja in ["0,883", "0,2635", "504", "700", "1.587,2", "0,568"]:
    check(aguja in cuerpo_docs, f"la documentacion menciona {aguja}")

readme = (ROOT / "README.md").read_text(encoding="utf-8")
check("aneel_orange_serie68_z.csv" in readme, "README menciona el export z de Orange")
check("requirements.txt" in readme, "README referencia requirements.txt")
check("run_all.ps1" in readme, "README referencia run_all.ps1")

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
print("\n" + "=" * 62)
if fallos:
    print(f"RESULTADO: {len(fallos)} fallo(s)")
    for f in fallos:
        print(f"  - {f}")
    sys.exit(1)
print("RESULTADO: todos los chequeos pasaron")
if avisos:
    print(f"({len(avisos)} aviso(s), no bloqueantes)")
print("=" * 62)
