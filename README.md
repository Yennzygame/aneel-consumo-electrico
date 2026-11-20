# Arquetipos de consumo eléctrico del mercado cativo brasileño

**ANEEL / SAMP · IND2622 — Ciência de Dados para Processos de Negócio · PUC-Rio**

Ronald Alvarez · Yennzy Barrera

**Repositorio:** https://github.com/Yennzygame/aneel-consumo-electrico

![Código QR del repositorio](docs/qr_repositorio.png)

---

## 1. Qué hace este proyecto

Agrupa el consumo eléctrico mensual del **mercado cativo regulado** brasileño en
arquetipos de comportamiento temporal, independientes del tamaño del segmento, y
traduce esos arquetipos en insumos para decisiones de retención, planificación y
seguimiento regulatorio.

**Pregunta de investigación.** ¿Qué arquetipos de comportamiento temporal se
pueden identificar empíricamente en el mercado cativo brasileño, con independencia
de la escala de consumo, y qué implican para la gestión de las distribuidoras?

**Unidad de análisis.** Segmento de mercado:

```
unidad = SigAgenteDistribuidora | DscClasseConsumoMercado
```

No es un consumidor individual: es el agregado mensual que ANEEL publica por
clase dentro de cada distribuidora. La representación matemática es una serie
temporal de 68 meses por unidad.

**Respuesta corta.** Tres arquetipos estables:

| Arquetipo | Unidades | % consumo | Tendencia | Crecimiento 12 m | Lectura |
|---|---:|---:|---:|---:|---|
| Contracción sostenida | 366 | 39,7 % | −1,12 %/mes | −43,0 % | La mayoría de los segmentos pierde consumo |
| Base estable | 187 | 44,7 % | +0,38 %/mes | +27,7 % | Pocos segmentos grandes y persistentes |
| Crecimiento acelerado | 147 | 15,6 % | +0,42 %/mes | +38,4 % | Iluminación pública y poder público |

La contracción del cativo (−12,8 % entre 2021 y los últimos 12 meses) coincide con
un mercado libre que crece +33,3 % y una generación distribuida que se multiplica
por 8,7. Es un cambio estructural, no un error de datos.

---

## 2. Resultados metodológicos que hay que poder defender

| Elemento | Resultado |
|---|---|
| Datos crudos | 6.671.150 filas, 18 columnas, 6 CSV (2021-01 a 2026-09) |
| Ventana analizada | 2021-01 a 2026-08 (68 meses; 2026-09 es parcial) |
| Cobertura | 833 unidades → 734 con clases analizables → **700 incluidas** (99,4 % del consumo) |
| Diseño de experimentos | **504 corridas** = 18 pipelines × 4 algoritmos × k = 2…8 |
| Comparación | métricas en el espacio de cada pipeline **y** en un espacio de referencia común de 68 meses |
| Estabilidad | submuestreo 80/20, **ARI = 0,883** con 100 repeticiones |
| Verificación Orange | réplica exacta del modelo final: **ARI = 1,0**, tamaños 366/187/147 |
| Modelo final | `serie68 \| winsor_z_fila \| kmeans \| k=3` |
| Silhouette | 0,2635 en su espacio · 0,2553 en espacio común |
| Asociación con clase | Cramér's V = 0,568 · tras quitar efecto clase = 0,195 · ARI = 0,333 |
| Separación de descriptores | todos significativos tras FDR; ε² hasta 0,72 |

**Corrección clave respecto del trabajo anterior.** `VlrMercado` no es una sola
variable: su unidad depende de `DscDetalheMercado` (R$, kWh, kW, %, conteos).
El proyecto anterior sumaba todas las unidades; el silhouette = 0,8899 era un
artefacto. Aquí se usa exclusivamente `Energia TUSD (kWh)`; `Energia TE (kWh)`
contiene el mismo kWh y sumarla lo duplicaría.

---

## 3. Mapa del repositorio

```
.
├── data/
│   ├── raw/                     # 6 CSV originales de ANEEL/SAMP (no versionados)
│   └── processed/               # panel, matrices, descriptores, PCA, metadatos
├── src/
│   ├── config.py                # rutas, filtros, ventana, semillas
│   ├── aneel_pipeline.py        # ingestión → panel → matrices → features
│   ├── doe.py                   # 504 corridas + MLflow + estabilidad
│   ├── select_final.py          # selección, arquetipos, tests, 13 figuras
│   └── analisis_mercado.py      # cativo vs libre vs GD
├── tools/
│   ├── orange_check.py          # verificación del modelo en Orange 3
│   └── verificar_entregables.py # auditoría de cifras y artefactos
├── notebooks/                   # 5 notebooks ejecutados, en español
│   ├── 01_calidad_y_unidad_analisis.ipynb
│   ├── 02_representaciones_y_normalizacion.ipynb
│   ├── 03_doe_y_mlflow.ipynb
│   ├── 04_resultados_y_decision.ipynb
│   └── 05_orange_verificacion.ipynb
├── docs/                        # diccionario, metodología, resultados, defensa, artículo
├── reports/
│   ├── figures/                 # 13 figuras PNG
│   ├── tables/                  # métricas, rankings, etiquetas, perfiles
│   ├── orange/                  # CSV listos para Orange
│   ├── html/                    # notebooks exportados a HTML
│   └── diagnostico/             # perfilado de los datos crudos
├── models/modelo_final.joblib   # pipeline + etiquetas serializadas
├── mlflow.db                    # tracking SQLite (experimentos DoE y final)
├── requirements.txt
└── run_all.ps1                  # reproducción completa en PowerShell
```

---

## 4. Cómo reproducirlo

### 4.1 Requisitos

```powershell
python -m pip install -r requirements.txt
```

Probado con Python 3.15.0, pandas 3.0.6, scikit-learn 1.9.1, MLflow 3.18.0,
matplotlib 3.11.2 (Windows 11).

### 4.2 Pipeline completo

```powershell
# 1. Panel unidad × mes, matrices y features (~1 min)
python -m src.aneel_pipeline --step all

# 2. DoE de 504 corridas con MLflow (~3-4 min)
python -m src.doe --full

# 3. Modelo final, arquetipos, tests y figuras (~1 min)
python -m src.select_final --auto

# 4. Contexto de mercado cativo/libre/GD (~1,5 min)
python -m src.analisis_mercado
```

O todo de una vez:

```powershell
.\run_all.ps1
```

Los pasos 1–4 son idempotentes: si el artefacto existe, lo reutilizan. Usar
`--force` para recalcular.

### 4.3 Notebooks

```powershell
python -m nbconvert --to notebook --execute --inplace notebooks\01_calidad_y_unidad_analisis.ipynb
# ... repetir para 02–05
```

Los notebooks ya están ejecutados con sus salidas. Se pueden abrir con Jupyter,
VS Code o `jupyter lab`.

### 4.4 MLflow

```powershell
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Abrir `http://127.0.0.1:5000`.

- Experimento `ANEEL_Clustering_DoE`: 504 corridas del grid.
- Experimento `ANEEL_Clustering_Final`: corrida del modelo elegido.

### 4.5 Verificación en Orange

Orange se ejecuta en un entorno separado (Python 3.14 + Orange 3.41) para no
mezclar dependencias de Qt con el entorno principal. La réplica del modelo final
reproduce la partición exacta (ARI = 1,0; tamaños 366/187/147; silhouette
0,2635) usando el CSV `aneel_orange_serie68_z.csv`. Una alternativa con los 19
descriptores produce ARI = 0,036 y un clúster de 6 unidades, lo que confirma que
esa representación no era apta para el problema.

```powershell
& "C:\Users\yennz\AppData\Local\Temp\opencode\venv-orange\Scripts\python" tools\orange_check.py
```

El resultado queda en `reports/tables/orange_verificacion.json`. El flujo paso a
paso está en `docs/08_guia_orange.md`.

### 4.6 Semillas y determinismo

`RANDOM_STATE = 42` en `src/config.py`. KMeans usa `n_init=10`; la estabilidad usa
submuestras generadas con `numpy.random.default_rng(42)`. Ward/Average/Complete
son deterministas. Las figuras usan el backend `Agg`.

### 4.7 Verificación de entregables

```powershell
python -m tools.verificar_entregables
```

Audita que existan los artefactos, que el DoE tenga 504 corridas únicas, que el
modelo final sea el top del ranking, que los tamaños 366/187/147 coincidan entre
`final_resumen.json`, `final_labels.csv` y la réplica Orange, y que los notebooks
tengan salidas. Falla con código ≠ 0 si algo se desincroniza.

Para exportar los notebooks a HTML:

```powershell
python -m nbconvert --to html --output-dir reports\html notebooks\*.ipynb
```

---

## 5. Documentación

| Documento | Contenido |
|---|---|
| [`docs/01_diccionario_datos.md`](docs/01_diccionario_datos.md) | Columnas, unidades, filtros, calidad y decisiones de limpieza |
| [`docs/02_metodologia.md`](docs/02_metodologia.md) | Unidad de análisis, features, DoE, métricas, selección y robustez |
| [`docs/03_resultados.md`](docs/03_resultados.md) | Tablas, figuras, interpretación y límites |
| [`docs/04_respuesta_criticas.md`](docs/04_respuesta_criticas.md) | Punto por punto: las 5 críticas de la reunión del 10-nov |
| [`docs/05_guion_defensa.md`](docs/05_guion_defensa.md) | Guion de 12 minutos con tiempos y preguntas difíciles |
| [`docs/06_trabajos_relacionados.md`](docs/06_trabajos_relacionados.md) | Literatura y vacío de investigación |
| [`docs/07_borrador_articulo.md`](docs/07_borrador_articulo.md) | Borrador SBPO/ENEGEP (≤ 15 páginas) |
| [`docs/08_guia_orange.md`](docs/08_guia_orange.md) | Flujo Orange 3 paso a paso y verificación |

---

## 6. Artefactos principales

| Archivo | Qué contiene |
|---|---|
| `reports/tables/doe_resultados.csv` | 504 corridas × 22 columnas de métricas |
| `reports/tables/doe_ranking.csv` | Ranking multicriterio y score |
| `reports/tables/final_resumen.json` | Métricas y perfiles del modelo final |
| `reports/tables/final_labels.csv` | Etiqueta y descriptores por unidad (700 filas) |
| `reports/tables/final_perfil_clusters.csv` | Tabla de arquetipos |
| `reports/tables/final_tests_descriptores.csv` | Kruskal–Wallis + FDR + ε² |
| `reports/tables/final_exposicion_distribuidoras.csv` | Riesgo por distribuidora (101) |
| `reports/tables/mercado_variacion.csv` | Cativo, libre y GD: 2021 vs últimos 12 m |
| `reports/figures/01…13_*.png` | Evidencia visual del pipeline |
| `reports/orange/aneel_orange.csv` | 700 × 41 para Orange (descriptores + etiqueta) |
| `reports/orange/aneel_orange_serie68.csv` | 700 × 72 (serie cruda de 68 meses + metadatos + etiqueta) |
| `reports/orange/aneel_orange_serie68_z.csv` | 700 × 73 (serie winsorizada y z por fila: réplica exacta del modelo) |
| `reports/tables/orange_verificacion.json` | Réplica Orange (ARI = 1,0) y alternativa con descriptores |

---

## 7. Límites declarados

1. El panel mide **consumo facturado en el cativo**, no consumo físico total ni
   autoconsumo. Un segmento puede caer porque migró al mercado libre.
2. La clase de consumo explica parte de la estructura: Cramér's V ajustado 0,195
   y ARI 0,333. Los arquetipos describen trayectoria, no sustituyen a la clase.
3. Quedan fuera 34 segmentos con cobertura < 95 % (0,6 % del consumo).
4. La acción recomendada por arquetipo requiere validación con especialistas de
   negocio; el proyecto entrega la señal y el tablero, no la política final.
5. Los datos terminan en 2026-08; no incorporan cambios posteriores.

---

## 8. Contexto académico

Trabajo final de **IND2622 — Ciência de Dados para Processos de Negócio**
(Prof. Dra. Fernanda Baião, PUC-Rio). Metodología de referencia: *Lean Data
Science Research Life Cycle* (Shcherbakov et al., 2014), con trazabilidad de
experimentos (MLflow) y verificación visual independiente (Orange).
