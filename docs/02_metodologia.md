# Metodología y diseño de experimentos

Este documento explica **por qué** cada decisión metodológica es como es, no solo
qué se hizo. Está pensado para defender el trabajo ante una revisión académica y
para que otra persona pueda reproducirlo.

---

## 1. Marco de investigación

Se adopta el *Lean Data Science Research Life Cycle* (Shcherbakov et al., 2014):

```
Entendimiento del problema
        ↓
Obtención y perfilado de datos
        ↓
Ciclo interno de investigación  ← DoE + MLflow
        ↓
Visualización y post-procesamiento
        ↓
Acciones de negocio
        ↓
Retroalimentación
```

El **ciclo interno** es el corazón metodológico: no se elige un algoritmo por
conveniencia, se diseña un experimento factorial, se registra cada corrida y se
selecciona con un criterio explícito.

---

## 2. Unidad de análisis

### 2.1 Definición conceptual

> **Segmento de mercado:** la combinación de una distribuidora y una clase de
> consumo, observada mensualmente.

```
u = (SigAgenteDistribuidora, DscClasseConsumoMercado)
X_u = [consumo_{2021-01}, …, consumo_{2026-08}] ∈ ℝ^68
```

No es un consumidor: ANEEL no publica microdatos por medidor. Es el agregado
mensual que el regulador sí publica y sobre el cual se toman decisiones de tarifa,
planificación y seguimiento.

### 2.2 Por qué esta unidad y no otra

| Alternativa | Problema |
|---|---|
| Consumidor individual | no existe en los datos abiertos |
| Distribuidora | mezcla residencial, industrial y rural; pierde la heterogeneidad que motiva el estudio |
| Clase a nivel nacional | borra diferencias entre concesiones |
| Estado / región | criterio geográfico que el proyecto busca superar |
| **Distribuidora × clase** | máxima granularidad publicada, comparable entre concesiones y accionable |

### 2.3 Utilidad decisional

El arquetipo permite responder:

- ¿Qué segmentos de una distribuidora están perdiendo consumo?
- ¿Cuánto del consumo cativo está expuesto a contracción?
- ¿Qué clases explican la caída: industrial, rural, comercial?
- ¿Dónde priorizar retención frente a migración al mercado libre?
- ¿Qué distribuidoras requieren revisión de proyección de demanda?

La unidad no es un cliente al que se le hace marketing, sino un **segmento de
mercado** al que se le asigna una política de seguimiento, una prioridad de
retención o una hipótesis de planificación. Esa es la diferencia que la profesora
pidió explicitar.

---

## 3. Preparación de datos

1. **Ingestión por chunks** (400.000 filas) para no cargar 6,67 M × 18 columnas en
   memoria.
2. **Parseo brasileño** de `VlrMercado`.
3. **Filtro de mercado**: `Regular` + `CATIVO`.
4. **Selección de variable**: solo `Energia TUSD (kWh)`.
5. **Agregación** por unidad × mes (suma de kWh, suma de consumidores).
6. **Panel** de 55.140 celdas y 833 unidades.
7. **Filtro de clases** (7 clases de mercado atendido) → 734 unidades.
8. **Cobertura ≥ 95 %** y huecos internos ≤ 2 meses → **700 unidades**.
9. **Interpolación lineal** solo de huecos internos pequeños.
10. **Ventana final** 2021-01 … 2026-08 (68 meses).

La interpolación se aplica después de decidir la inclusión: una unidad con más de
2 meses consecutivos faltantes se excluye, no se inventa.

---

## 4. Representaciones

Se comparan cinco familias, no una:

| Representación | Dimensión | Captura | Limitación |
|---|---:|---|---|
| `serie68` | 68 | forma completa, tendencia, estacionalidad, shocks | alta dimensionalidad |
| `estacional12` | 12 | patrón estacional promedio | pierde evolución |
| `descriptores` | 19 | resumen interpretable de forma | pierde detalle temporal |
| `pca2/pca3_serie` | 2–3 | forma comprimida | pierde varianza no explicada |
| `pca2/pca3_estacional` | 2–3 | estacionalidad comprimida | pierde tendencia |

### 4.1 Normalización

La normalización **por fila** elimina el nivel de consumo:

$$
z_{u,t} = \frac{y_{u,t} - \bar y_u}{s_u}
$$

Así dos segmentos con la misma forma pero 1000× de diferencia en MWh quedan
comparables. Se prueban también:

- `log_z_fila`: comprime asimetría antes de estandarizar.
- `minmax_fila`: lleva cada serie a [0, 1].
- `winsor_z_fila`: recorta el 1 % extremo de cada serie antes de estandarizar;
  reduce el efecto de picos atípicos.
- `z_columna`: estandariza cada mes contra la cross-section (compite, pero no
  elimina el tamaño).
- `robust_columna`, `minmax_columna`, `winsor_z_columna`: variantes para
  descriptores.

**No todas las combinaciones son válidas.** Aplicar z-score por fila a un vector
de descriptores heterogéneos (tendencia, drawdown, senos/cosenos) no tiene
sentido: se destruiría la información de cada descriptor. Por eso el DoE usa 18
pipelines válidos, no 40 combinaciones ciegas.

---

## 5. Diseño de experimentos

### 5.1 Factores

| Factor | Niveles | Justificación |
|---|---|---|
| Representación × escalado | 18 pipelines | probar forma completa, resumen y compresión |
| Algoritmo | KMeans, Ward, Average, Complete | particional vs jerárquico; distintos criterios de enlace |
| Número de clústeres | k = 2…8 | rango razonable para segmentación accionable |

**Total: 18 × 4 × 7 = 504 corridas.**

### 5.2 Por qué 504 y no 9

La crítica del 10-nov fue correcta: 9 ejecuciones no permiten separar el efecto de
la representación, del algoritmo, de `k` y del escalado. Con 504 corridas:

- cada factor se evalúa con los demás controlados;
- se puede construir un ranking y analizar sensibilidad;
- se detectan interacciones (por ejemplo, PCA funciona bien con KMeans pero mal
  con Average);
- la conclusión no depende de una sola elección afortunada.

No se afirma que 504 sea un factorial completo de todos los niveles posibles: es
un **factorial completo sobre 18 pipelines válidos**, que es el espacio de diseño
defendible. Añadir pipelines inválidos solo inflaría el número.

### 5.3 Comparación en espacio común

Un problema clásico: silhouette en 2 dimensiones (PCA) tiende a ser mayor que en
68 dimensiones, no porque la partición sea mejor, sino porque la geometría es más
simple. Para evitarlo, cada partición se evalúa en:

1. **Espacio propio** (`*_espacio`): la geometría usada para clusterizar.
2. **Espacio de referencia común** (`*_ref`): la serie de 68 meses estandarizada
   por fila, idéntica para todas las corridas.
3. **Espacio de referencia PCA-10** (`silhouette_ref_pca10`): control adicional de
   dimensionalidad.

La selección usa el espacio común. Es una decisión clave para que la comparación
sea justa. El efecto puede ser extremo: `descriptores | robust_columna |
average | k = 2` obtiene silhouette 0,980 en su espacio propio y 0,027 en el
espacio común. Rankear por la métrica propia habría seleccionado un artefacto
de geometría.

### 5.4 Métricas

| Métrica | Fórmula / idea | Dirección |
|---|---|---|
| Silhouette | $(b_i-a_i)/\max(a_i,b_i)$ promediado | ↑ |
| Davies–Bouldin | promedio de $(S_i+S_j)/M_{ij}$ | ↓ |
| Calinski–Harabasz | $\frac{tr(B)/(k-1)}{tr(W)/(n-k)}$ | ↑ |
| Inercia (WCSS) | suma de distancias al centroide | ↓ (solo KMeans) |
| Balance | $n_{\min}/n_{\max}$ | ↑ |
| Singletons | clústeres de tamaño 1 | = 0 |
| Estabilidad | ARI medio en submuestreo 80/20 | ↑ |

### 5.5 Estabilidad

Para cada corrida:

1. Se permutan las 700 unidades con semilla 42 + r.
2. Se entrena con el 80 %.
3. Se asignan las unidades retenidas al centroide más cercano.
4. Se calcula ARI contra la partición completa.
5. Se repite 10 veces en el DoE y 100 veces para el modelo final.

Esto responde a una pregunta que silhouette no responde: *¿la partición sobrevive
si cambian 20 % de los datos?*

### 5.6 Registro

Cada corrida se registra en MLflow (`mlflow.db`) con:

- parámetros: representación, escalado, algoritmo, k, features, muestras, semilla;
- métricas: todas las anteriores;
- tags: etapa, run_key;
- nombre de corrida: `representacion|escalado|algoritmo|kN`.

---

## 6. Selección del modelo

### 6.1 Filtros de interpretabilidad

Antes de puntuar se descartan:

- `k < 3` o `k > 6`;
- clúster mínimo < 3 % de las unidades;
- soluciones con singletons;
- `silhouette_ref < 0,10`.

Quedan **68 candidatas** de las 504.

**Por qué `k = 2` se excluye.** Con dos grupos solo se puede decir “alto vs bajo”,
que es precisamente el criterio que el proyecto quiere superar. La decisión
necesita distinguir contracción, estabilidad y crecimiento. Además, el score
penaliza la falta de parsimonia con una función explícita.

### 6.2 Score multicriterio

$$
\text{score} = 0{,}35\,s_{sil} + 0{,}25\,s_{est} + 0{,}15\,s_{DB}
+ 0{,}10\,s_{CH} + 0{,}10\,s_{bal} + 0{,}05\,s_{pars}
$$

donde cada $s$ es el rango percentil (1 = mejor) y $s_{pars}=1-(k-3)/3$.

Los pesos reflejan la prioridad del problema:

- 35 % separación (calidad del agrupamiento);
- 25 % estabilidad (credibilidad);
- 15 % Davies–Bouldin y 10 % Calinski (consistencia interna);
- 10 % balance (accionabilidad);
- 5 % parsimonia (interpretabilidad).

No son pesos “óptimos”: son una declaración explícita de preferencias. Cualquier
revisor puede cambiarlos y recalcular el ranking con
`src/select_final.puntuar_doe`.

### 6.3 Resultado

| Criterio | Valor |
|---|---|
| Modelo | `serie68 \| winsor_z_fila \| kmeans \| k=3` |
| Silhouette (espacio propio) | 0,2635 |
| Silhouette (espacio común) | 0,2553 |
| Davies–Bouldin (común) | 1,876 |
| Calinski–Harabasz (común) | 230,8 |
| Estabilidad (10 rep.) | 0,928 |
| Estabilidad (100 rep.) | **0,883** (sd 0,113) |
| Balance | 0,40 |
| Clúster mínimo | 21 % |

El máximo silhouette del grid es 0,312 con `k = 2`, pero no es una solución
accionable. Entre `k ≥ 3`, el modelo elegido es el mejor compromiso, no el máximo
de una sola métrica.

---

## 7. Validación estadística de los arquetipos

### 7.1 ¿Los grupos son distintos?

Kruskal–Wallis por descriptor (no asume normalidad):

$$
H = \frac{12}{N(N+1)}\sum_j \frac{R_j^2}{n_j} - 3(N+1)
$$

con corrección FDR de Benjamini–Hochberg. Tamaño de efecto:

$$
\varepsilon^2 = \frac{H - (k-1)}{N - k}
$$

Resultado: los 19 descriptores significativos tras FDR; los mayores efectos son
tendencia (0,72), crecimiento 12 m (0,71), YoY medio (0,62) y drawdown (0,29).

### 7.2 ¿Los grupos son solo la clase de consumo?

Tres pruebas:

1. **Cramér's V** entre arquetipo y clase: 0,568 (asociación fuerte).
2. **Re-clustering tras eliminar el efecto medio de la clase**: a cada unidad se
   le resta el centroide de su clase y se vuelve a correr KMeans.
3. **ARI** entre la partición original y la ajustada: 0,333.

Interpretación: la clase explica parte de la estructura, pero no toda. El
Cramér's V ajustado baja a 0,195 y sobrevive estructura propia. Es una limitación
declarada, no un resultado oculto.

### 7.3 ¿La contracción es real?

Se compara con el contexto de mercado:

| Serie | 2021 | Últimos 12 m | Variación |
|---|---:|---:|---:|
| Cativo regular | 24.677 GWh/mes | 21.521 GWh/mes | −12,8 % |
| Libre | 12.588 | 16.779 | +33,3 % |
| GD inyectada | 972 | 8.429 | +767 % |
| GD consumida | 1.057 | 5.980 | +466 % |

La caída del cativo coincide con migración al libre y autogeneración. Es
consistente con un cambio estructural del mercado.

---

## 8. Amenazas a la validez

| Amenaza | Cómo se mitiga | Límite que queda |
|---|---|---|
| Unidad mal definida | definición formal + 700 unidades auditables | no hay microdatos de consumidor |
| Escala domina | normalización por fila + comparación en espacio común | la forma no captura nivel |
| Sobreajuste al algoritmo | 4 algoritmos × 7 k × 18 pipelines | no se prueban todos los algoritmos existentes |
| Inestabilidad | submuestreo 80/20 con 100 repeticiones | no es validación temporal hacia adelante |
| Clase disfrazada | Cramér's V + ARI tras quitar efecto clase | asociación residual 0,195 |
| Datos parciales | exclusión de 2026-09 y cobertura ≥ 95 % | 34 unidades fuera |
| Interpretación causal | se habla de “compatible con migración”, no de causa | no hay datos de contratos del libre |

**Trabajo futuro natural:** validación temporal (*backtesting*: entrenar con
2021-2024 y evaluar estabilidad de etiquetas en 2025-2026), modelo predictivo de
migración y validación con especialistas de ANEEL/distribuidoras.

---

## 9. Reproducibilidad

- Semilla global 42.
- Pipeline idempotente por etapa.
- 504 corridas registradas en MLflow.
- Figuras y tablas regenerables con `python -m src.select_final --auto`.
- Notebooks ejecutados de punta a punta.
- Entorno documentado en `requirements.txt`.
- `run_all.ps1` reproduce todo en Windows/PowerShell.

---

## 10. Referencias metodológicas

- Shcherbakov, M. et al. (2014). *Lean Data Science Research Life Cycle.*
- Rousseeuw, P. (1987). Silhouettes: a graphical aid to cluster analysis.
- Davies, D. & Bouldin, D. (1979). A cluster separation measure.
- Caliński, T. & Harabasz, J. (1974). A dendrite method for cluster analysis.
- Hubert, L. & Arabie, P. (1985). Comparing partitions (ARI).
- Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate.
- Cramér, H. (1946). *Mathematical Methods of Statistics.*
