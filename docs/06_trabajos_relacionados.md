# Trabajos relacionados y posicionamiento

Este documento resume las corrientes de literatura relevantes, qué aporta cada una
y dónde se ubica este proyecto. No pretende ser una revisión exhaustiva: pretende
justificar las decisiones metodológicas y delimitar el vacío de investigación.

---

## 1. Clustering de curvas de carga

La literatura clásica de *load profiling* agrupa curvas de demanda para tarifas,
pronóstico y segmentación de clientes.

- **Chicco (2012)** revisa y compara métodos de agrupamiento de curvas de carga,
  con énfasis en la elección de la medida de distancia, la normalización y el
  número de grupos. Es la referencia más directa para justificar que **la
  normalización por fila y la comparación entre representaciones** no son un
  detalle, sino una decisión metodológica central.
- **Chicco, Napoli & Piglione (2006)** comparan técnicas de clustering para
  clasificación de clientes eléctricos y muestran que distintos algoritmos pueden
  producir particiones similares si la representación es adecuada. Eso respalda la
  idea de que **la representación pesa más que el algoritmo**, que es exactamente
  lo que aparece en el DoE de este proyecto.
- **Rhodes et al. (2014)** clusterizan perfiles residenciales y discuten la
  sensibilidad a la normalización y a la ventana temporal. Su conclusión es
  consistente con la nuestra: normalizar cambia el objeto de análisis de “cuánto”
  a “cómo”.
- **Haben, Singleton & Grindrod (2016)** usan datos de medidores inteligentes para
  identificar patrones de comportamiento y discuten la estabilidad de los grupos.
  Aportan el marco de validación que aquí se adapta con ARI y submuestreo.

**Diferencia con este proyecto.** Esa literatura trabaja con curvas horarias o
diarias de clientes individuales o de una muestra de hogares. Aquí la unidad es un
**segmento agregado distribuidora × clase**, con granularidad mensual y horizonte
de 68 meses. El problema no es “qué cliente se parece a cuál”, sino “qué segmento
de mercado se comporta igual a lo largo del tiempo”.

---

## 2. Clustering de series temporales

- **Liao (2005)** y **Aghabozorgi, Shirkhorshidi & Teh (2015)** sistematizan el
  clustering de series temporales: representación, medida de distancia, prototipo
  y validación. Este proyecto se apoya en esa taxonomía para justificar las cinco
  representaciones comparadas (serie completa, perfil estacional, descriptores,
  PCA de serie y PCA estacional).
- **Paparrizos & Gravano (2015)** proponen *k-Shape*, que alinea series y usa una
  medida de forma. Su crítica a la distancia euclidiana es válida, pero aquí las
  series están alineadas por mes calendario y normalizadas; no hay desfase
  arbitrario que justifique alineamiento dinámico. Se deja como extensión.
- **Teeraratkul, O'Neill & Lall (2017)** usan enfoques basados en forma para
  clustering y predicción de curvas de carga. Refuerzan la idea de que la forma
  normalizada es una representación válida y predictiva.

**Diferencia.** La mayoría de estos trabajos optimiza la representación para
pronóstico de corto plazo. Aquí el objetivo es **describir trayectorias de mercado
y sustentar decisiones**, por lo que la interpretabilidad de los descriptores y la
estabilidad de la partición pesan tanto como la métrica de separación.

---

## 3. Estabilidad y selección de modelos de clustering

- **Ben-David, von Luxburg & Pál (2006)** advierten que la estabilidad por sí sola
  no identifica el número correcto de clústeres. Por eso este proyecto **no usa la
  estabilidad como único criterio**: la combina con silhouette, Davies–Bouldin,
  Calinski–Harabasz y balance en un score multicriterio.
- **von Luxburg (2010)** y **Hennig (2007)** ofrecen marcos para evaluar
  estabilidad por remuestreo. El esquema 80/20 con ARI sigue esa línea.
- **Milligan & Cooper (1985)** comparan procedimientos para decidir el número de
  grupos; su conclusión es que ningún criterio domina en todos los escenarios. Eso
  justifica el enfoque multicriterio y la publicación del ranking completo.
- **Steinley (2006)** y **Jain (2010)** resumen fortalezas y límites de KMeans:
  eficiencia, sensibilidad a la inicialización y necesidad de fijar `k`. Aquí se
  mitiga con `n_init=10`, semilla fija y comparación con jerárquicos.

**Posicionamiento.** El proyecto no propone un nuevo algoritmo. Propone un **marco
de selección reproducible** para un problema aplicado, con un DoE amplio y
trazabilidad. Esa es una contribución metodológica, no algorítmica.

---

## 4. Pronóstico y planificación de demanda

- **Hong & Fan (2016)** revisan el pronóstico probabilístico de carga y muestran
  que la calidad del pronóstico depende de la segmentación previa y de la
  estabilidad de los patrones. Los arquetipos de este proyecto son un insumo
  natural para ese paso.
- La literatura de planificación de expansión suele usar modelos agregados por
  región o subsistema. Este trabajo ofrece una segmentación **transversal a la
  geografía**, basada en comportamiento, que puede alimentar escenarios
  diferenciados.

**Diferencia.** No se construye un modelo de pronóstico. Se construye la
**tipología** que un modelo de pronóstico o un plan de expansión puede usar para
no aplicar un supuesto único a todo el mercado.

---

## 5. Mercado eléctrico brasileño y datos abiertos

- **ANEEL/SAMP** publica mensualmente el mercado por distribuidora, clase, tipo de
  mercado y detalle. Es una fuente abierta, auditable y de cobertura nacional.
- El mercado se divide entre **ACR** (ambiente de contratación regulada, “cativo”)
  y **ACL** (ambiente de contratación libre). La migración de consumidores al ACL
  y la **generación distribuida** (compensación de energía) son fenómenos
  estructurales del período 2021-2026.
- La literatura brasileña suele analizar el mercado por subsistema, estado o
  agente, no por **segmento distribuidora × clase con foco en trayectoria**.

**Vacío.** No se encontró un trabajo que:

1. use datos abiertos regulatorios brasileños a nivel segmento distribuidora ×
   clase;
2. cubra un horizonte plurianual completo (68 meses);
3. compare sistemáticamente representaciones y algoritmos con un DoE amplio;
4. evalúe estabilidad por remuestreo y asociación con la clase;
5. traduzca los arquetipos en exposición por distribuidora y decisiones.

Ese conjunto es el aporte del proyecto.

---

## 6. Tabla de posicionamiento

| Corriente | Unidad | Horizonte | Foco | Este proyecto |
|---|---|---|---|---|
| Load profiling clásico | cliente / curva horaria | días-semanas | tarifa, segmentación | segmento agregado, 68 meses |
| Smart meter clustering | hogar | horas-días | comportamiento | mercado regulado agregado |
| Time-series clustering | serie genérica | variable | algoritmo | comparación de representaciones |
| Pronóstico de demanda | región / sistema | meses-años | precisión | tipología para escenarios |
| Regulación ANEEL | agente / subsistema | anual | cumplimiento | segmento × clase, trayectoria |

---

## 7. Contribuciones

1. **Empírica:** evidencia de tres arquetipos estables en el cativo brasileño y de
   una contracción extendida compatible con migración al libre/GD.
2. **Metodológica:** DoE de 504 corridas con comparación en espacio común,
   estabilidad por submuestreo y selección multicriterio documentada.
3. **Aplicada:** matriz de decisión y tablero de exposición por distribuidora.
4. **Reproducibilidad:** pipeline, notebooks ejecutados, MLflow, figuras y tablas
   regenerables.

---

## 8. Referencias

- Aghabozorgi, S., Shirkhorshidi, A. S., & Teh, Y. W. (2015). Time-series
  clustering – A decade review. *Information Systems*, 53, 16–38.
- ANEEL. *Sistema de Acompanhamento do Mercado de Energia Elétrica (SAMP)*.
  Dados abertos. https://dadosabertos.aneel.gov.br/
- Ben-David, S., von Luxburg, U., & Pál, D. (2006). A sober look at clustering
  stability. *Learning Theory (COLT)*.
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate.
  *Journal of the Royal Statistical Society B*, 57(1), 289–300.
- Caliński, T., & Harabasz, J. (1974). A dendrite method for cluster analysis.
  *Communications in Statistics*, 3(1), 1–27.
- Chicco, G. (2012). Overview and performance assessment of the clustering methods
  for electrical load pattern grouping. *Energy*, 42(1), 68–80.
- Chicco, G., Napoli, R., & Piglione, F. (2006). Comparisons among clustering
  techniques for electricity customer classification. *IEEE Transactions on Power
  Systems*, 21(2), 933–940.
- Davies, D. L., & Bouldin, D. W. (1979). A cluster separation measure. *IEEE
  Transactions on Pattern Analysis and Machine Intelligence*, 1(2), 224–227.
- Haben, S., Singleton, C., & Grindrod, P. (2016). Analysis and clustering of
  residential customers energy behavioral demand using smart meter data. *IEEE
  Transactions on Smart Grid*, 7(1), 136–144.
- Hennig, C. (2007). Cluster-wise assessment of cluster stability. *Computational
  Statistics & Data Analysis*, 52(1), 258–271.
- Hong, T., & Fan, S. (2016). Probabilistic electric load forecasting: A tutorial
  review. *International Journal of Forecasting*, 32(3), 914–938.
- Hubert, L., & Arabie, P. (1985). Comparing partitions. *Journal of
  Classification*, 2(1), 193–218.
- Jain, A. K. (2010). Data clustering: 50 years beyond K-means. *Pattern
  Recognition Letters*, 31(8), 651–666.
- Liao, T. W. (2005). Clustering of time series data—a survey. *Pattern
  Recognition*, 38(11), 1857–1874.
- Milligan, G. W., & Cooper, M. C. (1985). An examination of procedures for
  determining the number of clusters in a data set. *Psychometrika*, 50(2),
  159–179.
- Paparrizos, J., & Gravano, L. (2015). k-Shape: Efficient and accurate clustering
  of time series. *ACM SIGMOD*, 1855–1870.
- Rhodes, J. D., Cole, W. J., Upshaw, C. R., Edgar, T. F., & Webber, M. E. (2014).
  Clustering analysis of residential electricity demand profiles. *Applied
  Energy*, 135, 461–471.
- Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and
  validation of cluster analysis. *Journal of Computational and Applied
  Mathematics*, 20, 53–65.
- Shcherbakov, M. et al. (2014). Lean Data Science Research Life Cycle. Referencia
  metodológica citada en el material de IND2622.
- Steinley, D. (2006). K-means clustering: a half-century synthesis. *British
  Journal of Mathematical and Statistical Psychology*, 59(1), 1–34.
- Teeraratkul, T., O'Neill, D., & Lall, S. (2017). Shape-based approach to
  household electric load curve clustering and prediction. *IEEE Transactions on
  Smart Grid*, 9(5), 5196–5206.
- von Luxburg, U. (2010). Clustering stability: An overview. *Foundations and
  Trends in Machine Learning*, 2(3), 235–274.
