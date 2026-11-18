# Arquetipos de comportamiento temporal del consumo eléctrico en el mercado cativo brasileño: un marco reproducible de clustering y selección de modelos

**Ronald Alvarez · Yennzy Barrera**

IND2622 — Ciência de Dados para Processos de Negócio, PUC-Rio

*Borrador para SBPO / ENEGEP — extensión objetivo ≤ 15 páginas*

---

## Resumen

El mercado cativo regulado brasileño perdió 12,8 % de su consumo mensual entre
2021 y los últimos doce meses observados, mientras el mercado libre creció 33,3 %
y la generación distribuida se multiplicó por 8,7. Este trabajo pregunta qué
arquetipos de comportamiento temporal existen dentro de ese mercado y cómo se
traducen en decisiones para las distribuidoras. La unidad de análisis es el
segmento `distribuidora × clase de consumo`, observado como una serie mensual de
68 meses (2021-01 a 2026-08) construida a partir de los datos abiertos del SAMP
de ANEEL. Se diseña un experimento factorial de 504 corridas (18 pipelines de
representación y escalado × 4 algoritmos × k = 2…8), registrado en MLflow, con
métricas calculadas tanto en el espacio de cada pipeline como en un espacio de
referencia común de 68 dimensiones y con estabilidad medida por submuestreo
80/20. El modelo seleccionado —serie completa, winsorización y estandarización
por fila, KMeans, k = 3— alcanza silhouette 0,2635, estabilidad ARI 0,883 con 100
repeticiones y tres arquetipos interpretables: contracción sostenida (366
segmentos, 39,7 % del consumo), base estable (187; 44,7 %) y crecimiento
acelerado (147; 15,6 %). La asociación con la clase de consumo es fuerte
(Cramér's V = 0,568), pero sobrevive estructura propia tras remover el efecto
medio de la clase (V = 0,195; ARI = 0,333). La contracción es compatible con la
migración al mercado libre y con la autogeneración, no con un error de medición.
El aporte es metodológico y aplicado: un marco reproducible de comparación de
representaciones y una lectura de exposición del cativo por distribuidora.

**Palabras clave:** clustering de series temporales; mercado eléctrico; datos
abiertos; diseño de experimentos; ANEEL.

## Abstract

The Brazilian regulated captive electricity market lost 12.8 % of its monthly
consumption between 2021 and the last twelve observed months, while the free
market grew 33.3 % and distributed generation increased 8.7-fold. This paper
asks which temporal behaviour archetypes exist within that market and how they
translate into decisions for distribution utilities. The unit of analysis is the
`utility × consumption class` segment, observed as a 68-month series (2021-01 to
2026-08) built from ANEEL's open SAMP data. We design a factorial experiment of
504 runs (18 representation/scaling pipelines × 4 algorithms × k = 2…8),
tracked in MLflow, with metrics computed both in each pipeline's own space and in
a common 68-dimensional reference space, plus stability measured by 80/20
subsampling. The selected model —full series, row-wise winsorised z-score,
KMeans, k = 3— reaches silhouette 0.2635, ARI stability 0.883 over 100
repetitions, and three interpretable archetypes: sustained contraction (366
segments, 39.7 % of consumption), stable base (187; 44.7 %) and accelerated
growth (147; 15.6 %). Association with consumption class is strong (Cramér's
V = 0.568) but own structure survives after removing the class mean effect
(V = 0.195; ARI = 0.333). Contraction is consistent with migration to the free
market and self-generation, not with a measurement error. The contribution is
methodological and applied: a reproducible framework for comparing
representations and a captive-market exposure view by utility.

**Keywords:** time-series clustering; electricity market; open data; design of
experiments; ANEEL.

---

## 1. Introducción

El sector eléctrico brasileño se organiza en dos ambientes de contratación: el
ambiente de contratación regulada (ACR), donde el consumidor permanece *cativo*
de su distribuidora, y el ambiente de contratación libre (ACL), donde puede
negociar directamente con generadores y comercializadores. Desde 2021, la
expansión del ACL y de la generación distribuida (GD) modificó la composición
del mercado que las distribuidoras facturan. La pregunta relevante para la
gestión no es solo cuánto cae el cativo en agregado, sino **qué segmentos caen,
cuáles se mantienen y cuáles crecen**, y con qué intensidad.

La literatura de *load profiling* responde preguntas de forma para clientes
individuales con curvas horarias o diarias (Chicco, 2012; Haben et al., 2016).
La literatura de clustering de series temporales ofrece el marco de
representación, distancia y validación (Liao, 2005; Aghabozorgi et al., 2015),
pero rara vez se aplica a segmentos agregados de mercado con horizonte
plurianual. Los datos abiertos de ANEEL permiten ese ejercicio: el Sistema de
Acompanhamento do Mercado de Energia Elétrica (SAMP) publica mensualmente el
mercado por distribuidora, clase de consumo, tipo de mercado y detalle.

Este trabajo se pregunta:

> ¿Qué arquetipos de comportamiento temporal se pueden identificar
> empíricamente en el mercado cativo brasileño, con independencia de la escala
> de consumo, y qué implican para la gestión de las distribuidoras?

Responderla exige tres decisiones que la literatura trata por separado y que
aquí se integran: (i) definir una unidad de análisis auditable; (ii) comparar
sistemáticamente representaciones y algoritmos en lugar de elegir uno; y (iii)
verificar que la partición no sea un reflejo de la clase de consumo ni un
artefacto de normalización.

Las contribuciones son:

1. **Empírica.** Evidencia de tres arquetipos estables en el cativo brasileño y
   de una contracción extendida compatible con la migración al libre y la GD.
2. **Metodológica.** Un diseño factorial de 504 corridas con evaluación en
   espacio común, estabilidad por remuestreo y ranking multicriterio explícito.
3. **Aplicada.** Una matriz de decisión y una vista de exposición del cativo por
   distribuidora que traduce el arquetipo en prioridad de gestión.
4. **Reproducibilidad.** Pipeline, notebooks, tracking de experimentos, figuras
   y tablas regenerables con semilla fija.

El resto del artículo se organiza así: la sección 2 discute trabajos
relacionados; la 3 describe datos y unidad de análisis; la 4 presenta el diseño
experimental y las métricas; la 5 reporta resultados; la 6 discute
implicaciones; la 7 declara amenazas a la validez; la 8 concluye.

---

## 2. Trabajos relacionados

**Clustering de curvas de carga.** Chicco (2012) muestra que la normalización y
la medida de distancia pesan tanto como el algoritmo en la calidad del
agrupamiento de perfiles eléctricos. Chicco et al. (2006) comparan técnicas de
clasificación de clientes y concluyen que representaciones adecuadas producen
particiones similares con algoritmos distintos. Rhodes et al. (2014) y Haben et
al. (2016) aplican clustering a perfiles residenciales y discuten sensibilidad
a la normalización y estabilidad de los grupos. Esa literatura trabaja con
clientes individuales y curvas horarias; aquí la unidad es un agregado de
mercado con granularidad mensual.

**Clustering de series temporales.** Liao (2005) y Aghabozorgi et al. (2015)
sistematizan representación, distancia, prototipo y validación. Paparrizos y
Gravano (2015) proponen *k-Shape* para alinear series; en este problema las
series están alineadas por mes calendario y normalizadas, por lo que el desfase
arbitrario que motiva el alineamiento dinámico no aparece. Teeraratkul et al.
(2017) refuerzan que la forma normalizada es una representación válida y
predictiva.

**Selección y estabilidad.** Ben-David et al. (2006) advierten que la
estabilidad por sí sola no identifica el número correcto de grupos; Hennig
(2007) y von Luxburg (2010) ofrecen marcos de evaluación por remuestreo;
Milligan y Cooper (1985) muestran que ningún criterio domina en todos los
escenarios. De ahí que este trabajo combine silhouette, Davies–Bouldin,
Calinski–Harabasz, balance y estabilidad en un score multicriterio, en lugar de
optimizar una sola métrica.

**Pronóstico y planificación.** Hong y Fan (2016) muestran que la calidad del
pronóstico depende de la segmentación previa y de la estabilidad de los
patrones. Este trabajo no construye un pronóstico: construye la tipología que un
modelo de pronóstico o un plan de expansión puede usar para no aplicar un
supuesto único a todo el mercado.

**Vacío.** No se encontró un trabajo que use datos abiertos regulatorios
brasileños a nivel segmento `distribuidora × clase`, cubra 68 meses, compare
sistemáticamente representaciones y algoritmos, evalúe estabilidad y asociación
con la clase, y traduzca el resultado en exposición por distribuidora. Ese
conjunto es el aporte.

---

## 3. Datos y unidad de análisis

### 3.1 Fuente

Se utilizan los seis archivos anuales del SAMP (2021 a 2026), con 6.671.150
filas y 18 columnas. Cada fila cruda describe un registro de mercado por
distribuidora, clase, tipo de mercado, detalle y mes. La ventana analizada es
2021-01 a 2026-08 (68 meses); 2026-09 se excluye porque el corte de generación
deja ese mes parcial (2,4 TWh frente a ~20 TWh de un mes completo).

### 3.2 El problema de `VlrMercado`

`VlrMercado` es una columna genérica: su unidad depende de
`DscDetalheMercado`. Puede contener R$, kWh, kW, porcentajes o conteos. Sumarla
sin separar el detalle mezcla unidades físicas y produce resultados inválidos.
En este trabajo se usa exclusivamente `Energia TUSD (kWh)`; `Energia TE (kWh)`
contiene el mismo kWh y sumar ambas duplicaría el consumo. Los conteos de
consumidores se usan solo como descriptor de tamaño, nunca como consumo.

### 3.3 Unidad de análisis

La unidad es el **segmento de mercado**:

$$
u = (\text{SigAgenteDistribuidora},\ \text{DscClasseConsumoMercado}),
\qquad
X_u = [y_{u,2021\text{-}01}, \dots, y_{u,2026\text{-}08}] \in \mathbb{R}^{68}
$$

No es un consumidor individual: ANEEL no publica microdatos por medidor. Es el
agregado mensual que el regulador sí publica y sobre el cual se toman decisiones
de tarifa, planificación y seguimiento. La Tabla 1 resume el embudo de filas.

**Tabla 1.** Del dato crudo a la matriz de análisis.

| Etapa | Resultado |
|---|---:|
| Filas crudas (6 CSV) | 6.671.150 |
| Filas `Regular` + `CATIVO` | 2.116.425 |
| Filas de `Energia TUSD (kWh)` | 302.717 |
| Celdas del panel (unidad × mes) | 55.140 |
| Unidades potenciales | 833 |
| Unidades con clases analizables | 734 |
| **Unidades incluidas** | **700** |
| Distribuidoras | 101 |
| Consumo incluido | 1.587,2 TWh |
| Cobertura del consumo filtrado | 99,4 % |

Se retienen siete clases de mercado atendido (Residencial, Comercial,
Industrial, Rural, Poder público, Iluminação pública y Serviço público),
unificando la variante tipográfica `Serviço Público`. Se excluyen `No se
aplica` (agregados administrativos) y `Consumo propio` (no es mercado
atendido). Se exige cobertura ≥ 95 % y huecos internos ≤ 2 meses; 34 unidades
quedan fuera (10,2 TWh, 0,6 % del consumo filtrado). Solo se interpola
linealmente huecos internos pequeños; una unidad con más de dos meses
consecutivos faltantes se excluye, no se inventa.

**Precaución de normalización.** `Número de consumidores` (CATIVO) y `Número de
Consumidores` (otros mercados) difieren en mayúsculas y representan universos
distintos; no se normalizan a minúsculas porque hacerlo mezclaría poblaciones.

---

## 4. Metodología

### 4.1 Marco

Se adopta el *Lean Data Science Research Life Cycle* (Shcherbakov et al., 2014).
El ciclo interno —diseño de experimentos, registro y selección— es el núcleo
metodológico: no se elige un algoritmo por conveniencia, se diseña un
experimento factorial y se selecciona con un criterio explícito.

### 4.2 Representaciones y escalado

Se comparan cinco familias de representación (Tabla 2). La normalización
principal es por fila,

$$
z_{u,t} = \frac{\tilde{y}_{u,t} - \bar{y}_u}{s_u},
$$

donde $\tilde{y}$ aplica winsorización al 1 % extremo de cada serie. Esto elimina
el nivel de consumo: dos segmentos con la misma forma pero tres órdenes de
magnitud de diferencia quedan comparables. Se prueban además `log_z_fila`,
`minmax_fila`, `z_columna` y variantes robustas. No todas las combinaciones son
válidas: aplicar z-score por fila a descriptores heterogéneos destruiría su
información, por lo que el diseño usa **18 pipelines válidos**, no todas las
combinaciones posibles.

**Tabla 2.** Representaciones comparadas.

| Representación | Dimensión | Captura | Limitación |
|---|---:|---|---|
| `serie68` | 68 | forma completa, tendencia, estacionalidad, shocks | alta dimensionalidad |
| `estacional12` | 12 | patrón estacional promedio | pierde evolución |
| `descriptores` | 19 | resumen interpretable | pierde detalle temporal |
| `pca2/pca3_serie` | 2–3 | forma comprimida | pierde varianza no explicada |
| `pca2/pca3_estacional` | 2–3 | estacionalidad comprimida | pierde tendencia |

Los 19 descriptores incluyen tendencia (pendiente y R²), crecimiento a 12 meses,
media y desviación de variaciones año a año, drawdown máximo, coeficiente de
variación, rango p90–p10, IQR relativo, proporción de meses bajo el percentil 80
y sobre el percentil 120, autocorrelaciones, amplitud y fuerza estacional, y
codificación circular del pico y del valle.

### 4.3 Diseño de experimentos

**Tabla 3.** Factores del diseño.

| Factor | Niveles | Justificación |
|---|---|---|
| Representación × escalado | 18 pipelines | forma completa, resumen y compresión |
| Algoritmo | KMeans, Ward, Average, Complete | particional vs jerárquico; distintos enlaces |
| Número de clústeres | k = 2…8 | rango razonable para segmentación accionable |

Total: 18 × 4 × 7 = **504 corridas**, ejecutadas en 3,1 min y registradas en
MLflow con parámetros, métricas y tags. Un diseño de nueve corridas no permite
separar el efecto de la representación, del escalado, del algoritmo y de k; con
504 cada factor se evalúa con los demás controlados y se detectan interacciones
—por ejemplo, PCA compite bien con KMeans y pierde con Average—. No se afirma un
factorial de todos los niveles imaginables: es un factorial completo sobre el
espacio de pipelines defendible.

### 4.4 Métricas y comparación en espacio común

Un problema clásico es que el silhouette en dos dimensiones (PCA) tiende a ser
mayor que en 68 dimensiones no porque la partición sea mejor, sino porque la
geometría es más simple. Por eso cada partición se evalúa en:

1. el **espacio propio** del pipeline, y
2. un **espacio de referencia común**: la serie de 68 meses estandarizada por
   fila, idéntica para las 504 corridas,
3. más un control adicional en PCA de 10 componentes.

Se reportan silhouette, Davies–Bouldin, Calinski–Harabasz, inercia (solo
KMeans), balance $n_{\min}/n_{\max}$, número de singletons y estabilidad.

### 4.5 Estabilidad

Para cada corrida se permutan las 700 unidades con semilla fija, se entrena con
el 80 %, se asignan las unidades retenidas al centroide más cercano y se calcula
el Adjusted Rand Index (Hubert y Arabie, 1985) contra la partición completa. Se
repite 10 veces en el grid y 100 veces para el modelo final. Esto responde una
pregunta que el silhouette no responde: *¿la partición sobrevive si cambian 20 %
de los datos?*

### 4.6 Selección

Antes de puntuar se descartan soluciones con k < 3 o k > 6, clúster mínimo < 3 %
de las unidades, singletons o silhouette en espacio común < 0,10. Quedan 68
candidatas. El score es

$$
\text{score} = 0{,}35\,s_{sil} + 0{,}25\,s_{est} + 0{,}15\,s_{DB}
+ 0{,}10\,s_{CH} + 0{,}10\,s_{bal} + 0{,}05\,s_{pars},
$$

donde cada $s$ es un rango percentil (1 = mejor) y
$s_{pars} = 1 - (k-3)/3$. Los pesos no son óptimos: son una declaración
explícita de preferencias —35 % separación, 25 % estabilidad, 15 %
Davies–Bouldin, 10 % Calinski, 10 % balance, 5 % parsimonia— que cualquier
revisor puede modificar y recalcular.

### 4.7 Validación estadística

Se aplica Kruskal–Wallis por descriptor (no asume normalidad) con corrección FDR
de Benjamini–Hochberg y tamaño de efecto
$\varepsilon^2 = [H-(k-1)]/(N-k)$. Para verificar que los arquetipos no sean
solo la clase de consumo se calcula Cramér's V, se resta a cada unidad el
centroide de su clase y se re-clusteriza, y se mide el ARI entre la partición
original y la ajustada.

---

## 5. Resultados

### 5.1 Diseño de experimentos

La Tabla 4 muestra el top 5 del ranking. Las tres primeras posiciones son la
misma representación (`serie68`) con distintas normalizaciones. PCA queda cerca
en silhouette común pero pierde estabilidad y no aporta interpretabilidad. Los
algoritmos jerárquicos rinden peor en estabilidad media (Ward 0,557; Average
0,672; Complete 0,521) frente a KMeans (0,845).

**Tabla 4.** Top 5 del ranking de 504 corridas (métricas en espacio común).

| run_key | k | Silhouette | Davies–Bouldin | Estabilidad | Balance | Score |
|---|---:|---:|---:|---:|---:|---:|
| `serie68\|winsor_z_fila\|kmeans\|k3` | 3 | 0,2553 | 1,876 | 0,928 | 0,402 | **0,902** |
| `serie68\|z_fila\|kmeans\|k3` | 3 | 0,2548 | 1,896 | 0,911 | 0,425 | 0,894 |
| `serie68\|log_z_fila\|kmeans\|k3` | 3 | 0,2519 | 1,891 | 0,935 | 0,423 | 0,889 |
| `pca2_serie\|none\|kmeans\|k3` | 3 | 0,2548 | 1,918 | 0,897 | 0,439 | 0,878 |
| `pca3_serie\|none\|kmeans\|k3` | 3 | 0,2548 | 1,932 | 0,900 | 0,442 | 0,868 |

El máximo de silhouette del grid es 0,312 con k = 2, pero se descarta: con dos
grupos solo se distingue “alto vs bajo”, no contracción, estabilidad y
crecimiento, y el score penaliza k < 3 por diseño. **No se eligió el máximo de
una métrica; se eligió el mejor compromiso documentado.** Este es un punto
metodológico central: el máximo de silhouette no es la respuesta cuando el
objetivo es decidir.

### 5.2 Modelo final

`serie68 | winsor_z_fila | kmeans | k = 3`.

**Tabla 5.** Métricas del modelo seleccionado.

| Métrica | Valor |
|---|---:|
| Silhouette (espacio propio) | 0,2635 |
| Silhouette (espacio común) | 0,2553 |
| Davies–Bouldin (común) | 1,876 |
| Calinski–Harabasz (común) | 230,8 |
| Inercia | 26.027,4 |
| Estabilidad (10 rep.) | 0,928 |
| Estabilidad (100 rep.) | **0,883** (sd 0,113) |
| Estabilidad de semilla | 0,967 |
| Balance | 0,402 |
| Clúster mínimo | 21 % |

### 5.3 Arquetipos

**Tabla 6.** Perfil de los tres arquetipos.

| | Contracción sostenida | Base estable | Crecimiento acelerado |
|---|---:|---:|---:|
| Unidades | 366 | 187 | 147 |
| % de unidades | 52,3 % | 26,7 % | 21,0 % |
| Consumo total (TWh) | 629,8 | 710,0 | 247,3 |
| % del consumo | 39,7 % | 44,7 % | 15,6 % |
| CV medio | 0,329 | 0,190 | 0,213 |
| Tendencia (%/mes) | **−1,125** | +0,377 | +0,417 |
| Crecimiento 12 m | **−43,0 %** | +27,7 % | +38,4 % |
| Amplitud estacional | 0,347 | 0,375 | 0,336 |
| Fuerza estacionalidad | 0,178 | 0,445 | 0,311 |
| Autocorrelación anual | 0,615 | 0,685 | 0,504 |
| Consumidores (prom.) | 12,2 M | 58,4 M | 15,8 M |

**Contracción sostenida** (366 unidades, 39,7 % del consumo). Tendencia
−1,12 %/mes y caída de 43 % en los últimos doce meses; el 100 % de sus unidades
tiene tendencia negativa. Es el grupo más numeroso pero no el de mayor consumo:
son segmentos pequeños y medianos, con mayor CV (0,329), es decir, una caída
ruidosa y estacional. Composición: Industrial 91, Rural 79, Comercial 77,
Serviço público 63, Iluminação pública 44.

**Base estable** (187 unidades, 44,7 % del consumo). Tendencia +0,38 %/mes,
crecimiento +27,7 % y alta persistencia anual (0,685). Menor CV (0,190):
comportamiento predecible. Composición: Residencial 81, Poder público 57,
Comercial 20. Concentra 58,4 millones de consumidores: es el grueso de la base
residencial. No significa “sin riesgo”: varias distribuidoras grandes tienen
este grupo como dominante y aun así tendencia ponderada negativa.

**Crecimiento acelerado** (147 unidades, 15,6 % del consumo). Tendencia
+0,42 %/mes y crecimiento +38,4 %, con alta volatilidad (desvío de variaciones
YoY 0,495). Composición: Iluminação pública 56, Poder público 36, Serviço
público 21. Está dominado por EQUATORIAL GO (17,8 %), ENEL CE (15,5 %) y
EQUATORIAL PA (12,7 %). El crecimiento se concentra en consumo público, no en
industria ni residencia.

**Tabla 7.** Composición por clase de consumo.

| Clase | Contracción | Base estable | Crecimiento |
|---|---:|---:|---:|
| Comercial | 77 | 20 | 4 |
| Iluminação pública | 44 | 0 | 56 |
| Industrial | 91 | 0 | 6 |
| Poder público | 8 | 57 | 36 |
| Residencial | 4 | 81 | 16 |
| Rural | 79 | 14 | 8 |
| Serviço público | 63 | 15 | 21 |

La asociación es fuerte (V = 0,568) pero no perfecta: hay cuatro unidades
residenciales en contracción y seis industriales en crecimiento.

### 5.4 Validación estadística

Los 19 descriptores sobreviven a FDR (Tabla 8). Los tamaños de efecto mayores
corresponden a tendencia (0,721), crecimiento a 12 meses (0,714), media de
variaciones YoY (0,621) y drawdown (0,287). La separación es de **trayectoria**,
no de estacionalidad ni de ruido.

**Tabla 8.** Kruskal–Wallis por descriptor (extracto).

| Descriptor | H | p | ε² | q FDR |
|---|---:|---:|---:|---:|
| `tendencia_pct_mes` | 504,8 | 2,4e-110 | **0,721** | 4,6e-109 |
| `crecimiento_12m` | 499,3 | 3,8e-109 | **0,714** | 3,6e-108 |
| `yoy_media` | 434,6 | 4,2e-95 | 0,621 | 2,6e-94 |
| `drawdown_max` | 202,3 | 1,2e-44 | 0,287 | 5,5e-44 |
| `fuerza_estacionalidad` | 175,4 | 8,0e-39 | 0,249 | 3,0e-38 |
| `ac1` | 147,6 | 9,0e-33 | 0,209 | 2,8e-32 |

**¿Solo la clase?** Cramér's V = 0,568 (p = 2,9e-89) indica asociación fuerte.
Tras restar el centroide de cada clase y re-clusterizar, V baja a 0,195
(p = 3,7e-07) y el ARI entre particiones es 0,333. La clase explica una parte
relevante, pero el arquetipo conserva estructura propia. Se reporta como
limitación, no se oculta.

**Estabilidad.** ARI medio 0,883 con 100 submuestras (sd 0,113). La distribución
no tiene colas catastróficas: incluso los peores submuestreos mantienen una
estructura reconocible. La estabilidad de semilla es 0,967.

**Verificación independiente.** El mismo modelo exportado y reconstruido en
Orange 3 reproduce exactamente la partición (ARI = 1,0; tamaños 366/187/147;
silhouette 0,2635). Esta réplica valida la exportación y la configuración, no un
algoritmo distinto —Orange usa el mismo KMeans de scikit-learn—. Una alternativa
con descriptores produce ARI = 0,036 y un clúster de 6 unidades, coherente con
que esa representación quedó fuera del grid por tamaño mínimo y balance. La
verificación confirma que el resultado no depende de una configuración manual
del entorno.

### 5.5 Contexto de mercado

**Tabla 9.** Mercado regular y GD: 2021 frente a los últimos 12 meses.

| Serie | 2021 (GWh/mes) | Últimos 12 m (GWh/mes) | Variación |
|---|---:|---:|---:|
| **Regular CATIVO** | 24.677 | 21.521 | **−12,8 %** |
| Regular LIVRE | 12.588 | 16.779 | +33,3 % |
| GD energía inyectada | 972 | 8.429 | +767,3 % |
| GD energía consumida | 1.057 | 5.980 | +465,6 % |
| Regular SUPRIMENTO | 340 | 218 | −35,9 % |
| Regular DISTRIBUIÇÃO | 413 | 480 | +16,3 % |

La caída del cativo no es un artefacto: coincide con el crecimiento del libre y
de la GD. El mercado cativo pierde participación frente a alternativas de
autogeneración y contratos libres. El panel mide **consumo facturado en el
cativo**, no consumo físico total ni autoconsumo; un segmento que migra al libre
“cae” en el cativo aunque siga consumiendo. Por eso se habla de **exposición del
cativo**, no de caída del consumo físico.

### 5.6 Exposición por distribuidora

**Tabla 10.** Exposición de las cinco mayores distribuidoras.

| Distribuidora | Consumo (TWh) | % en contracción | Tendencia ponderada | Clúster dominante |
|---|---:|---:|---:|---|
| ELETROPAULO | 156,0 | 34,1 % | −0,06 %/mes | Base estable |
| CEMIG-D | 123,0 | 42,1 % | −0,36 % | Base estable |
| CPFL-PAULISTA | 103,4 | 39,5 % | −0,37 % | Base estable |
| COPEL-DIS | 98,8 | 48,2 % | −0,45 % | Base estable |
| COELBA | 87,5 | 29,8 % | −0,23 % | Base estable |

De las 101 distribuidoras, 49 tienen base estable como clúster dominante, 36
contracción y 16 crecimiento. Las mayores tienen base estable como dominante,
pero entre 30 % y 48 % de su consumo está en el grupo de contracción. Se
reportan **dos vistas**: conteo de unidades —qué tan extendido está el
fenómeno— y consumo ponderado —cuánto pesa económicamente—. Una lectura solo
por conteo subestima el riesgo; una lectura solo por consumo oculta que la
contracción afecta a la mayoría de los segmentos.

---

## 6. Discusión

### 6.1 Lectura de negocio

El resultado no es “el cativo cae”. Es más específico: **la mayoría de los
segmentos cae, pero el consumo está concentrado en segmentos estables**. Esa
asimetría es la que permite decidir. La Tabla 11 traduce cada arquetipo en señal,
prioridad, acción e indicador de seguimiento.

**Tabla 11.** Matriz de decisión por arquetipo.

| Arquetipo | Señal | Prioridad | Acción | Indicador |
|---|---|---|---|---|
| Contracción sostenida | −1,12 %/mes; −43 % en 12 m | Alta | Revisar precio/contrato y riesgo de fuga al libre; priorizar retención en segmentos grandes | Δ consumo trimestral; share cativo vs libre |
| Base estable | tendencia ~0; alta persistencia | Media | Mantener y monitorear cambios de régimen | alerta si tendencia absoluta > 0,5 %/mes |
| Crecimiento acelerado | +38 % en 12 m; iluminación/poder público | Media-alta | Asegurar capacidad y cobertura; revisar proyección | error de pronóstico; % de crecimiento |

La unidad permite cinco usos concretos: retención de mercado cativo
(identificar segmentos en contracción y su peso), revisión tarifaria (comparar
distribuidoras con mezcla de arquetipos similar), planificación de red (separar
crecimiento acelerado de base estable), proyección de demanda (aplicar supuesto
de tendencia por arquetipo, no uno global) y seguimiento regulatorio (alertar
cambios de régimen por segmento). No es un cliente al que se le hace marketing:
es un segmento al que se le asigna política de seguimiento y prioridad.

### 6.2 Por qué el diseño experimental importa

El ranking muestra que la representación pesa más que el algoritmo: las cinco
primeras posiciones comparten `serie68`, y KMeans domina en estabilidad a los
jerárquicos. Si se hubiera elegido una sola combinación —como en un diseño de
nueve corridas— no se podría afirmar esto. El espacio común evita además la
ilusión de que PCA “separa mejor” porque su silhouette en dos dimensiones es
mayor (0,476 frente a 0,264 en el espacio propio): evaluado en las 68
dimensiones, PCA cae a 0,255 y pierde estabilidad. El caso extremo es
`descriptores | robust_columna | average | k = 2`: silhouette 0,980 en su espacio
propio y 0,027 en el espacio común. Sin esa corrección se habría elegido un
artefacto de geometría, no un hallazgo.

### 6.3 Posicionamiento frente a la literatura

Frente al *load profiling* clásico, este trabajo cambia la unidad —de cliente a
segmento de mercado— y el horizonte —de horas a 68 meses—. Frente al clustering
de series temporales, no propone un algoritmo nuevo sino un **marco de selección
reproducible** con comparación de representaciones, espacio común y
estabilidad. Frente a la literatura regulatoria brasileña, que suele analizar
por subsistema, estado o agente, aporta una segmentación transversal a la
geografía basada en comportamiento. La tipología no reemplaza al pronóstico: lo
alimenta con supuestos diferenciados.

---

## 7. Amenazas a la validez y límites

**Tabla 12.** Amenazas y mitigaciones.

| Amenaza | Mitigación | Límite que queda |
|---|---|---|
| Unidad mal definida | definición formal + 700 unidades auditables | no hay microdatos de consumidor |
| Escala domina | normalización por fila + espacio común | la forma no captura nivel |
| Sobreajuste al algoritmo | 4 algoritmos × 7 k × 18 pipelines | no se prueban todos los algoritmos |
| Inestabilidad | submuestreo 80/20 con 100 repeticiones | no es validación temporal hacia adelante |
| Clase disfrazada | Cramér's V + ARI tras quitar efecto clase | asociación residual 0,195 |
| Datos parciales | exclusión de 2026-09 y cobertura ≥ 95 % | 34 unidades fuera (0,6 %) |
| Interpretación causal | se habla de “compatible con migración” | no hay datos de contratos del libre |

Tres límites merecen énfasis. Primero, la clase de consumo explica parte de la
estructura: los arquetipos describen trayectoria, no sustituyen a la clase.
Segundo, el cativo mide consumo facturado; la migración al libre y la GD
explican la caída agregada, pero el panel no permite atribuir causalidad a nivel
de segmento. Tercero, la estabilidad se mide remuestreando unidades, no meses:
la validación temporal hacia adelante —entrenar con 2021-2024 y evaluar
persistencia de etiquetas en 2025-2026— es el trabajo futuro natural, junto con
un modelo predictivo de migración y validación con especialistas de ANEEL y
distribuidoras.

---

## 8. Conclusiones

El mercado cativo brasileño se puede segmentar en tres arquetipos estables y
accionables, con independencia de la escala de consumo. La contracción sostenida
concentra la mayoría de los segmentos (52,3 %) pero no la mayoría del consumo
(39,7 %); la base estable concentra el consumo (44,7 %) con pocas unidades
grandes y persistentes; el crecimiento acelerado es minoritario y está dominado
por consumo público. La contracción coincide con migración al libre y expansión
de la GD, y es robusta a remuestreo (ARI 0,883), significativa en descriptores
(FDR) y distinta de la clase de consumo (V ajustado 0,195; ARI 0,333).

El aporte principal no es un número de clústeres, sino un **marco reproducible
para decidir**: unidad de análisis explícita, 504 corridas registradas, métricas
en espacio común, estabilidad por remuestreo, ranking multicriterio y
traducción a exposición por distribuidora. Ese marco es transferible a otros
mercados regulados y a otros horizontes temporales. Las decisiones que habilita
—retención, revisión tarifaria, planificación y proyección— requieren validación
con especialistas de negocio; el proyecto entrega la señal, el tablero y la
trazabilidad, no la política final.

---

## Referencias

Aghabozorgi, S., Shirkhorshidi, A. S., & Teh, Y. W. (2015). Time-series
clustering – A decade review. *Information Systems*, 53, 16–38.

ANEEL. *Sistema de Acompanhamento do Mercado de Energia Elétrica (SAMP)*. Dados
abertos. https://dadosabertos.aneel.gov.br/

Ben-David, S., von Luxburg, U., & Pál, D. (2006). A sober look at clustering
stability. *Learning Theory (COLT)*.

Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate.
*Journal of the Royal Statistical Society B*, 57(1), 289–300.

Caliński, T., & Harabasz, J. (1974). A dendrite method for cluster analysis.
*Communications in Statistics*, 3(1), 1–27.

Chicco, G. (2012). Overview and performance assessment of the clustering methods
for electrical load pattern grouping. *Energy*, 42(1), 68–80.

Chicco, G., Napoli, R., & Piglione, F. (2006). Comparisons among clustering
techniques for electricity customer classification. *IEEE Transactions on Power
Systems*, 21(2), 933–940.

Davies, D. L., & Bouldin, D. W. (1979). A cluster separation measure. *IEEE
Transactions on Pattern Analysis and Machine Intelligence*, 1(2), 224–227.

Haben, S., Singleton, C., & Grindrod, P. (2016). Analysis and clustering of
residential customers energy behavioral demand using smart meter data. *IEEE
Transactions on Smart Grid*, 7(1), 136–144.

Hennig, C. (2007). Cluster-wise assessment of cluster stability. *Computational
Statistics & Data Analysis*, 52(1), 258–271.

Hong, T., & Fan, S. (2016). Probabilistic electric load forecasting: A tutorial
review. *International Journal of Forecasting*, 32(3), 914–938.

Hubert, L., & Arabie, P. (1985). Comparing partitions. *Journal of
Classification*, 2(1), 193–218.

Jain, A. K. (2010). Data clustering: 50 years beyond K-means. *Pattern
Recognition Letters*, 31(8), 651–666.

Liao, T. W. (2005). Clustering of time series data—a survey. *Pattern
Recognition*, 38(11), 1857–1874.

Milligan, G. W., & Cooper, M. C. (1985). An examination of procedures for
determining the number of clusters in a data set. *Psychometrika*, 50(2),
159–179.

Paparrizos, J., & Gravano, L. (2015). k-Shape: Efficient and accurate clustering
of time series. *ACM SIGMOD*, 1855–1870.

Rhodes, J. D., Cole, W. J., Upshaw, C. R., Edgar, T. F., & Webber, M. E. (2014).
Clustering analysis of residential electricity demand profiles. *Applied
Energy*, 135, 461–471.

Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and
validation of cluster analysis. *Journal of Computational and Applied
Mathematics*, 20, 53–65.

Shcherbakov, M. et al. (2014). *Lean Data Science Research Life Cycle*.
Referencia metodológica de IND2622.

Steinley, D. (2006). K-means clustering: a half-century synthesis. *British
Journal of Mathematical and Statistical Psychology*, 59(1), 1–34.

Teeraratkul, T., O'Neill, D., & Lall, S. (2017). Shape-based approach to
household electric load curve clustering and prediction. *IEEE Transactions on
Smart Grid*, 9(5), 5196–5206.

von Luxburg, U. (2010). Clustering stability: An overview. *Foundations and
Trends in Machine Learning*, 2(3), 235–274.

---

## Nota de preparación del manuscrito

Este borrador está escrito en español y usa tablas y ecuaciones en Markdown para
facilitar su revisión. Para someterlo a SBPO o ENEGEP:

1. **Idioma.** ENEGEP acepta portugués, español e inglés; SBPO acepta portugués
   e inglés. Si el destino es SBPO, traducir el cuerpo al portugués o al inglés
   y conservar el resumen en el otro idioma.
2. **Formato.** Aplicar la plantilla oficial (A4, márgenes y tipografía de la
   convocatoria) y verificar el límite de páginas de la edición vigente.
3. **Figuras.** Insertar, como mínimo: `03_doe_calidad_estabilidad.png` (504
   corridas), `05_curva_k.png` (codo y silhouette), `07_pca_scatter.png` (PC1
   vs PC2), `08_centroides.png` (trayectorias), `10_composicion_clases.png` y
   `13_mercado_cativo_livre_gd.png`. Exportar a 300 dpi.
4. **Tablas.** Las Tablas 4, 6, 9 y 10 son las indispensables; las demás pueden
   pasar a material suplementario si el límite de páginas aprieta.
5. **Datos y código.** Incluir la URL del repositorio o un apéndice de
   reproducibilidad con los cuatro comandos del pipeline y la semilla 42.
6. **Citación de datos.** Citar ANEEL/SAMP con la fecha de extracción y la
   ventana 2021-01 a 2026-08, indicando la exclusión de 2026-09 por mes parcial.

**Extensión estimada del cuerpo actual:** 13–14 páginas en formato de una
columna con las seis figuras indicadas y las tablas 4, 6, 9 y 10.
