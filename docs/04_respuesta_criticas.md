# Respuesta a las críticas de la reunión del 10 de noviembre

La reunión con la profesora dejó cinco objeciones. Este documento las responde una
por una, con la cita, el diagnóstico, la corrección implementada y la evidencia
verificable.

---

## Crítica 1 — “No entiendo cuál es la unidad de análisis”

> *“No estoy consiguiendo entender qué es cada dato: ¿es un consumidor, una
> distribuidora, un binomio, qué es? […] Cada línea de la tabla ¿qué es?”*

### Diagnóstico

La respuesta anterior (“es el binomio distribuidora × clase”) era correcta pero
insuficiente: no decía **qué contiene cada fila**, **qué representa cada columna**
ni **por qué esa unidad y no otra**. Además, la presentación mezclaba la matriz
cruda con la matriz normalizada y no quedaba claro qué se estaba agrupando.

### Corrección

1. **Definición formal y explícita:**

   ```
   unidad = distribuidora × clase de consumo
   X_u = [consumo_2021-01, …, consumo_2026-08] ∈ ℝ^68
   ```

   Cada fila es un **segmento de mercado**, no un consumidor. Cada columna es un
   mes. El valor es el consumo facturado en el mercado cativo, en MWh.

2. **Diccionario de datos completo:** `docs/01_diccionario_datos.md` describe las
   18 columnas crudas, las 6 derivadas y las 19 features.

3. **Embudo de filas:** 6.671.150 → 2.116.425 → 302.717 → 55.140 → 700.

4. **Trazabilidad en notebook:** `notebooks/01_calidad_y_unidad_analisis.ipynb`
   muestra una fila cruda, el problema de `VlrMercado` y la construcción del panel.

### Evidencia

- 700 unidades, 101 distribuidoras, 99,4 % del consumo filtrado.
- Tabla de unidades incluida en `reports/tables/final_labels.csv`.
- Figura `02_unidades.png`.

### Respuesta oral (20 s)

> “Cada fila es un segmento: una distribuidora y una clase de consumo. No es un
> consumidor porque ANEEL no publica microdatos. Cada columna es un mes; la fila
> completa es la serie de 68 meses de ese segmento. Agrupamos segmentos, no
> clientes, y eso es lo que permite decidir sobre tarifas, retención y
> planificación.”

---

## Crítica 2 — “¿Para qué sirve agrupar eso? ¿Qué haces diferente con cada grupo?”

> *“Si agrupo clientes, puedo hacer campañas distintas. Si agrupo alumnos, puedo
> pensar jornadas distintas. Para la unidad que ustedes agrupan, ¿qué pueden hacer
> de forma diferente? No estoy entendiendo el problema.”*

### Diagnóstico

El proyecto anterior mostraba clústeres pero no consecuencias. “Tres arquetipos”
no es una decisión. Faltaba el puente entre resultado y acción.

### Corrección

Se construyó una **matriz de decisión** explícita:

| Arquetipo | Señal | Prioridad | Acción | Indicador |
|---|---|---|---|---|
| Contracción sostenida | −1,12 %/mes; −43 % en 12 m | Alta | Revisar precio/contrato y riesgo de fuga al libre; priorizar retención en segmentos grandes | Δ consumo trimestral; share cativo vs libre |
| Base estable | tendencia ~0; alta persistencia | Media | Mantener y monitorear cambios de régimen | alerta si la tendencia absoluta > 0,5 %/mes |
| Crecimiento acelerado | +38 % en 12 m; iluminación/poder público | Media-alta | Asegurar capacidad y cobertura; revisar proyección | error de pronóstico; % de crecimiento |

Además, se agregó la vista por distribuidora
(`reports/tables/final_exposicion_distribuidoras.csv`), que traduce el arquetipo a
**exposición del cativo**:

- 36 distribuidoras tienen la contracción como grupo dominante.
- Las cinco mayores tienen entre 30 % y 48 % de su consumo en contracción.
- El cuadrante tendencia × volatilidad permite priorizar revisión de tarifa y
  planificación de red.

### Por qué la unidad sí permite decidir

| Decisión | Cómo se usa el arquetipo |
|---|---|
| Retención de mercado cativo | identificar segmentos en contracción y su peso |
| Revisión tarifaria | comparar distribuidoras con mezcla de arquetipos similar |
| Planificación de red | separar crecimiento acelerado de base estable |
| Proyección de demanda | aplicar supuesto de tendencia por arquetipo, no uno global |
| Seguimiento regulatorio | alertar cambios de régimen por segmento |

### Evidencia

- `docs/03_resultados.md` §4 y §7.
- `notebooks/04_resultados_y_decision.ipynb` §6.
- Figura `11_exposicion_distribuidoras.png`.

### Respuesta oral (25 s)

> “El arquetipo no es un cliente: es un segmento de mercado. Con él, una
> distribuidora sabe qué parte de su cativo está en contracción, cuánto pesa y en
> qué clase. Eso alimenta tres decisiones: retención, revisión tarifaria y
> proyección de demanda. La matriz de decisión está en el documento y el tablero
> por distribuidora también.”

---

## Crítica 3 — “Nueve escenarios son insuficientes”

> *“Un plan de experimentación de un proyecto de ciencia de datos con nueve
> ejecuciones es muy poco. No alcanza para garantizar robustez. […] Tienen que
> explicar cuántos escenarios se ejecutaron de verdad.”*

### Diagnóstico

Correcto. Nueve corridas no permiten separar representación, escalado, algoritmo y
`k`. Además, el número estaba mal presentado: se hablaba de “9 escenarios” cuando
en realidad eran 9 combinaciones de una matriz más amplia.

### Corrección

**504 corridas** con factorial completo sobre 18 pipelines válidos:

```
18 pipelines (representación × escalado)
× 4 algoritmos (KMeans, Ward, Average, Complete)
× 7 valores de k (2…8)
= 504
```

- Todas registradas en MLflow (`ANEEL_Clustering_DoE`).
- Métricas en espacio propio y en espacio de referencia común.
- Estabilidad por submuestreo 80/20 en todas las corridas.
- Ranking multicriterio con filtros de interpretabilidad (68 candidatas).

### Evidencia

| Elemento | Dónde |
|---|---|
| 504 corridas crudas | `reports/tables/doe_resultados.csv` |
| Ranking | `reports/tables/doe_ranking.csv` |
| Top 20 | `reports/tables/doe_top20.csv` |
| Registro MLflow | `mlflow.db` (experimento `ANEEL_Clustering_DoE`) |
| Análisis | `notebooks/03_doe_y_mlflow.ipynb` |
| Metodología | `docs/02_metodologia.md` §5 |

### Respuesta oral (20 s)

> “La crítica era correcta. Pasamos de 9 a 504 corridas: 18 pipelines de
> representación y escalado, por 4 algoritmos, por k de 2 a 8. Cada corrida está
> en MLflow con sus métricas y su estabilidad. No elegimos la primera que funcionó:
> hay un ranking y un criterio explícito.”

---

## Crítica 4 — “El scatter plot tenía la misma variable en X y en Y”

> *“Aquel gráfico tenía la misma variable en el eje X y en el eje Y. ¿Cuál es el
> objetivo de poner un gráfico que tenga la misma variable en X y en Y?”*

### Diagnóstico

El gráfico anterior enfrentaba dos columnas que en la práctica representaban lo
mismo (o casi), por lo que la “separación perfecta” era un artefacto visual. No
tenía ejes interpretables ni una proyección justificada.

### Corrección

La figura `07_pca_scatter.png` ahora usa **PC1 vs PC2** de la serie estandarizada
por fila:

- PC1 y PC2 son componentes ortogonales, no la misma variable.
- El porcentaje de varianza explicada se reporta en los ejes.
- El color es el arquetipo asignado por el modelo final.
- La separación se lee como estructura en el plano, no como identidad de ejes.

Además, la evidencia principal de separación ya no es el scatter: son los
**centroides normalizados** (`08_centroides.png`) y las **distribuciones de
descriptores** (`09_descriptores.png`), que muestran la separación en las variables
que realmente usa el clustering.

### Evidencia

- `reports/figures/07_pca_scatter.png` (PC1 vs PC2, con varianza en ejes).
- `reports/figures/08_centroides.png`.
- `notebooks/04_resultados_y_decision.ipynb` §1.
- Código: `src/select_final.py`, función `fig_pca`.

### Respuesta oral (15 s)

> “Tenían razón: el scatter anterior no tenía ejes interpretables. Lo reemplazamos
> por PC1 vs PC2, con la varianza explicada en cada eje y el color del arquetipo.
> Pero la evidencia fuerte no es el scatter: son los centroides y los descriptores,
> que muestran la separación en las 68 dimensiones que usa el modelo.”

---

## Crítica 5 (transversal) — “Son series temporales y las agrupan sin mirar la temporalidad”

> *“Tengo la impresión de que sus datos son series temporales y ustedes están
> agrupando cosas que en realidad son series temporales, sin mirar la temporalidad
> de ese dato.”*

### Diagnóstico

La matriz de 69 columnas **sí** conserva la temporalidad, pero la presentación no
lo hacía evidente y la normalización podía interpretarse como una pérdida de la
secuencia.

### Corrección

1. **La representación principal es la serie completa de 68 meses**, no un resumen
   transversal. Cada columna es un mes y el orden importa.
2. **Features temporales explícitas:** tendencia, crecimiento 12 m, YoY, drawdown,
   autocorrelaciones, estacionalidad y codificación circular del pico/valle.
3. **Centroides temporales:** `08_centroides.png` muestra la trayectoria media de
   cada arquetipo a lo largo de los 68 meses.
4. **La ventana se declara:** 2021-01 a 2026-08; 2026-09 se excluye por parcial.
5. **La estabilidad se mide remuestreando unidades**, no meses; se declara como
   limitación y se propone validación temporal hacia adelante como trabajo futuro.

### Evidencia

- `notebooks/02_representaciones_y_normalizacion.ipynb` §1 y §2.
- `docs/01_diccionario_datos.md` §6.3.
- `reports/figures/08_centroides.png`.

### Respuesta oral (20 s)

> “Sí miramos la temporalidad: la unidad es la serie completa de 68 meses y las
> features son de trayectoria, no de un corte transversal. El clustering agrupa
> formas de series. La estabilidad que reportamos es por remuestreo de unidades;
> la validación temporal hacia adelante es el siguiente paso, y la declaramos como
> límite.”

---

## Resumen antes / después

| Crítica | Antes | Ahora |
|---|---|---|
| Unidad de análisis | “binomio” sin definición operativa | definición formal + 700 unidades auditables + diccionario |
| Utilidad | 3 clústeres sin consecuencias | matriz de decisión + exposición por distribuidora |
| DoE | 9 escenarios | 504 corridas + espacio común + estabilidad + MLflow |
| Scatter | ejes duplicados / no interpretables | PC1 vs PC2 + centroides + descriptores |
| Temporalidad | no explicitada | serie de 68 meses + features de trayectoria + límite declarado |

---

## Lo que se reconoce como límite (no se oculta)

1. La clase explica parte de la estructura (V ajustado 0,195; ARI 0,333).
2. El cativo mide consumo facturado, no consumo físico.
3. No hay validación temporal hacia adelante todavía.
4. La acción recomendada necesita validación con negocio.
5. Orange queda como verificación visual en entorno separado, no como motor del
   resultado.

Reconocer estos límites es parte de la respuesta: la profesora no pidió ocultar
incertidumbre, pidió claridad sobre qué se está agrupando y para qué.
