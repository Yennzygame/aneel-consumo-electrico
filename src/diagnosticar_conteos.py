"""Inspecciona la estructura de filas de 'Número de consumidores' y de energia
para decidir como agregar sin duplicar conteos.
"""
from __future__ import annotations

import pandas as pd

PATH = r"C:\Users\yennz\OneDrive\Documentos\Ciencia de Datos\data\raw\samp-2024.csv"
USE = [
    "DatCompetencia", "VlrMercado", "NomTipoMercado", "DscDetalheMercado",
    "DscOpcaoEnergia", "DscClasseConsumoMercado", "SigAgenteDistribuidora",
    "DscPostoTarifario", "DscSubGrupoTarifario", "DscModalidadeTarifaria",
    "DscSubClasseConsumidor", "DscDetalheConsumidor",
]


def parse_br(s):
    s = s.astype(str).str.strip()
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma, s.str.replace(".", "", regex=False))
    return pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")


parts = []
for ch in pd.read_csv(PATH, sep=";", encoding="latin1", usecols=USE,
                      chunksize=400_000, dtype=str, low_memory=False):
    ch = ch[(ch["NomTipoMercado"] == "Regular") & (ch["DscOpcaoEnergia"] == "CATIVO")]
    ch["val"] = parse_br(ch["VlrMercado"])
    parts.append(ch)
df = pd.concat(parts, ignore_index=True)
print("filas Regular+CATIVO 2024:", len(df))

cons = df[df["DscDetalheMercado"] == "Número de consumidores"]
print("\nPostos en conteo de consumidores:", cons["DscPostoTarifario"].unique())
print("Modalidades:", cons["DscModalidadeTarifaria"].unique())
print("Subgrupos:", cons["DscSubGrupoTarifario"].unique())
print("Subclases:", cons["DscSubClasseConsumidor"].unique()[:20])
print("Detalle consumidor:", cons["DscDetalheConsumidor"].unique()[:20])

key = ["SigAgenteDistribuidora", "DscClasseConsumoMercado", "DatCompetencia"]
g = cons.groupby(key).agg(n_filas=("val", "size"), suma=("val", "sum"),
                          maximo=("val", "max"), n_postos=("DscPostoTarifario", "nunique"),
                          n_subclases=("DscSubClasseConsumidor", "nunique"))
print("\nDistribucion de n_filas por (agente,clase,mes):")
print(g["n_filas"].value_counts().sort_index().head(20))
print("n_postos:", g["n_postos"].value_counts().to_dict())
print("n_subclases:", g["n_subclases"].value_counts().head(10).to_dict())
print("Casos suma>max:", int((g["suma"] > g["maximo"]).sum()), "de", len(g))

ej = cons.groupby(key).filter(lambda x: len(x) > 1).head(20)
print("\nEjemplo de filas repetidas:")
print(ej[["SigAgenteDistribuidora", "DscClasseConsumoMercado", "DatCompetencia",
          "DscSubClasseConsumidor", "DscPostoTarifario", "DscModalidadeTarifaria",
          "val"]].to_string(index=False))

# Energia: revisar duplicidad por subclase/postos
en = df[df["DscDetalheMercado"] == "Energia TUSD (kWh)"]
print("\nEnergia TUSD: postos", en["DscPostoTarifario"].unique(),
      "| n filas", len(en))
ge = en.groupby(key).size()
print("n_filas por unidad-mes:", ge.value_counts().sort_index().head(10).to_dict())
ej2 = en.groupby(key).filter(lambda x: len(x) > 1).head(12)
print(ej2[["SigAgenteDistribuidora", "DscClasseConsumoMercado", "DatCompetencia",
           "DscSubClasseConsumidor", "DscPostoTarifario", "DscModalidadeTarifaria",
           "val"]].to_string(index=False))
