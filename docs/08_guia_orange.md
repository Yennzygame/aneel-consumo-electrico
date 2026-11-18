# Guía de Orange 3

Orange se usa como **verificación visual independiente**, no como motor del
resultado. El clustering se produce en Python, se registra en MLflow y se valida
con pruebas estadísticas; Orange permite que un analista repita el flujo con nodos
y compruebe que la estructura aparece sin escribir código.

---

## 1. Estado real de la verificación

Se instaló Orange en un entorno separado:

```
Python 3.14.7
Orange 3.41.0
```

y se ejecutó `tools/orange_check.py`. Resultado:

| Prueba | ARI vs proyecto | Tamaños | Silhouette | Lectura |
|---|---:|---|---:|---|
| Réplica del modelo final (`aneel_orange_serie68_z.csv`) | **1,000** | 366 / 187 / 147 | 0,2635 | el CSV normalizado y la configuración reproducen la partición exacta |
| Alternativa con 19 descriptores + Normalize por columna | 0,036 | 509 / 185 / 6 | — | los descriptores no son una base estable para k = 3 |

**Matiz honesto.** Orange usa internamente el mismo KMeans de scikit-learn, así que
ARI = 1 valida la **exportación, la normalización y la configuración**, no un
algoritmo distinto. El valor de la verificación está en que un tercero puede abrir
el CSV en Orange Canvas y obtener la misma estructura.

El JSON completo está en `reports/tables/orange_verificacion.json`.

---

## 2. Archivos entregados

| Archivo | Filas × columnas | Para qué |
|---|---|---|
| `reports/orange/aneel_orange_serie68_z.csv` | 700 × 73 | **réplica exacta** del modelo final (serie winsorizada y z por fila) |
| `reports/orange/aneel_orange_serie68.csv` | 700 × 72 | serie cruda en MWh, para explorar escalas |
| `reports/orange/aneel_orange.csv` | 700 × 41 | etiqueta + 19 descriptores + PC1–PC3 + 12 meses |

Columnas de metadatos en los tres: `unidad`, `agente`, `clase`, `cluster`,
`cluster_nombre`.

---

## 3. Por qué no se entrega un `.ows`

El archivo `ferramenta_orange.ows` del proyecto anterior está en **XML de Orange 2**
y no abre en Orange 3. Convertirlo a mano es propenso a errores de esquema y un
workflow corrupto es peor que ninguno.

La alternativa es reconstruirlo en 2 minutos con los pasos de abajo. El CSV ya
contiene todo lo necesario; el workflow no aporta información nueva, solo la
disposición visual.

Si se necesita un `.ows` para la entrega, se puede guardar desde Orange Canvas
después de seguir la Opción A y adjuntarlo como evidencia de la sesión.

---

## 4. Instalación de Orange (entorno separado)

No instalar Orange en el entorno principal del proyecto: el pipeline corre con
Python 3.15 / pandas 3.0 / scikit-learn 1.9 y Orange arrastra versiones propias.

```powershell
py -3.14 -m venv .venv-orange
.venv-orange\Scripts\activate
python -m pip install orange3
```

Verificar:

```powershell
python -c "import Orange; print(Orange.__version__)"
```

En este equipo: `3.41.0`.

Para ejecutar la verificación:

```powershell
.venv-orange\Scripts\python tools\orange_check.py
```

---

## 5. Flujo A — réplica exacta en Orange Canvas

1. **File**
   - Abrir `reports/orange/aneel_orange_serie68_z.csv`.
   - *Info* debe mostrar 700 instancias y 73 variables.

2. **Select Columns**
   - **Target**: `cluster_nombre` (categórica, para colorear).
   - **Features**: las 68 columnas `2021-01` … `2026-08`.
   - **Metas**: `unidad`, `agente`, `clase`, `cluster`.
   - **No** incluir `cluster_nombre` ni `cluster` como features.

3. **k-Means**
   - Number of clusters: **3**
   - Initialization: **k-means++**
   - Number of initializations: **10**
   - Maximum iterations: 300
   - Random seed: **42**
   - *No* marcar “Normalize features”.

4. **Distances**
   - Metric: **Euclidean**.
   - Conectar desde la salida de **File** (no desde k-Means).

5. **Silhouette**
   - Conectar **Distances** → *Distances*.
   - Conectar **k-Means** → *Cluster labels*.

6. **Scatter Plot**
   - Abrir `aneel_orange.csv` en un segundo **File**.
   - Ejes: **PC1** y **PC2**.
   - Color: `cluster_nombre`.
   - Esto reemplaza el scatter anterior de ejes duplicados.

7. **Box Plot**
   - Variable: `tendencia_pct_mes`.
   - Agrupar por `cluster_nombre`.
   - Debe mostrar la contracción separada del resto.

8. **Data Table**
   - Revisar `unidad`, `cluster_nombre`, `tendencia_pct_mes`,
     `crecimiento_12m`.

### Resultado esperado

| Cluster de Orange | Tamaño | Equivalente |
|---|---:|---|
| 0 | 366 | Contracción sostenida |
| 1 | 187 | Base estable |
| 2 | 147 | Crecimiento acelerado |

Silhouette ≈ **0,2635**. ARI contra `final_labels.csv` = **1,000**.

---

## 6. Flujo B — control con descriptores

Útil para mostrar por qué la representación importa.

1. **File** → `reports/orange/aneel_orange.csv`.
2. **Select Columns**
   - Target: `cluster_nombre`.
   - Features: los 19 descriptores (`cv` … `valle_cos`).
   - Excluir `total_mwh`, `consumidores_medios`, `PC1`, `PC2`, `PC3`.
3. **Preprocess** → *Normalize Features* (por columna).
4. **k-Means** → k = 3, seed 42.
5. **Silhouette** y **Scatter Plot**.

Resultado observado: un clúster de **6 unidades** y ARI = 0,036 contra el modelo
final. No es un fallo de Orange: es la misma lección del DoE, donde los
descriptores con normalización por columna quedaron fuera por tamaño mínimo y
balance.

---

## 7. Por qué no se usa “Normalize by row” en Orange

Orange normaliza **por columna** (cada feature entre instancias), no por fila
(cada serie contra su propia media). Para el modelo final se necesita lo segundo:
si se normaliza por columna, se mezcla la escala de distintos meses y no se elimina
el tamaño del segmento.

Por eso el pipeline exporta `aneel_orange_serie68_z.csv` ya normalizado por fila.
Es la forma correcta de replicar el resultado en Orange sin depender de una opción
que la herramienta no ofrece.

---

## 8. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Un solo clúster con 700 unidades | `cluster` o `cluster_nombre` quedó como feature | revisar *Select Columns* |
| Clústeres por tamaño (gigantes vs pequeños) | se usó el CSV en MWh, no `_z` | abrir `aneel_orange_serie68_z.csv` |
| Silhouette muy alto (0,8+) | se está evaluando en 2 PCs o con ejes duplicados | usar *Distances* sobre las 68 features |
| k-Means no converge | datos con NaN | el CSV no tiene NaN; revisar importación |
| Los tamaños no coinciden | semilla o `n_init` distintos | seed 42, n_init 10 |
| Orange no abre el `.ows` antiguo | es XML de Orange 2 | reconstruir con esta guía |

---

## 9. Qué demuestra Orange y qué no

**Demuestra**

- El CSV exportado es consistente y legible por una herramienta externa.
- La configuración k = 3 reproduce la partición.
- Un analista sin Python puede ver los grupos y sus descriptores.

**No demuestra**

- Que el algoritmo sea distinto: es el mismo KMeans.
- Que la partición sea válida por sí sola: eso lo sostienen el DoE, la estabilidad
  y las pruebas estadísticas.
- Que la decisión de negocio sea correcta: eso requiere validación con expertos.

Orange es una pieza de trazabilidad y comunicación, no la fuente de verdad.
