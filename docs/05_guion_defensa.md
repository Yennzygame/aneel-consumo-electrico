# Guion de defensa — 12 minutos

**Proyecto:** arquetipos de consumo eléctrico del mercado cativo (ANEEL/SAMP)
**Curso:** IND2622 · Prof. Dra. Fernanda Baião

Regla de oro: cada minuto responde una pregunta. Si el tiempo se acorta, se
sacrifican detalles, nunca la unidad de análisis ni el DoE.

---

## 0:00–0:40 · Apertura

> “Buenos días. El proyecto agrupa el consumo eléctrico mensual del mercado cativo
> brasileño en arquetipos de comportamiento, independientes del tamaño del
> segmento. La unidad de análisis es el segmento distribuidora × clase de consumo,
> no el consumidor individual. El resultado son tres arquetipos estables que
> permiten priorizar retención, revisión tarifaria y planificación. Todo el
> análisis es reproducible y está registrado.”

**Slide 1:** título, autores, pregunta de investigación en una línea.

---

## 0:40–2:00 · Problema y cliente

> “ANEEL y las distribuidoras analizan el mercado por región o por estado. Eso
> oculta que dos concesiones del mismo estado pueden tener dinámicas opuestas. La
> pregunta es: ¿qué arquetipos temporales existen, con independencia de la escala?
> El cliente es ANEEL y las áreas de estrategia de las distribuidoras. La decisión
> concreta es dónde priorizar retención, cómo comparar concesiones en revisión
> tarifaria y qué supuesto de demanda usar en planificación.”

**Slide 2:** problema, cliente, decisión, pregunta.

No entrar todavía en algoritmos.

---

## 2:00–3:30 · Unidad de análisis (la diapositiva más importante)

> “Cada fila es un segmento: una distribuidora y una clase de consumo. Por ejemplo,
> LIGHT | Industrial. No es un consumidor porque ANEEL no publica microdatos. Cada
> columna es un mes; la fila completa es la serie de 68 meses. El valor es consumo
> facturado en el mercado cativo, en MWh.
>
> La unidad es agrupable porque cada fila describe el mismo tipo de objeto:
> un segmento de mercado con una serie temporal. Y es accionable porque las
> decisiones de tarifa, retención y planificación se toman exactamente a ese nivel.
> No agrupamos clientes: agrupamos segmentos.”

**Slide 3:** diagrama de una fila → serie → 700 filas; embudo 6,67 M → 700.

**Si preguntan “¿por qué no un consumidor?”:** “Porque el dato abierto no existe a
ese nivel; el mínimo publicado es distribuidora × clase. Inventar un consumidor
sería falsificar la unidad.”

---

## 3:30–5:00 · Datos y calidad

> “Seis CSV, 6,67 millones de filas, 18 columnas, 2021 a 2026. El hallazgo de
> calidad más importante: `VlrMercado` no es una sola variable. Su unidad depende
> del detalle: reales, kWh, kW, porcentajes y conteos. El trabajo anterior sumaba
> todo; eso producía un número sin unidad y un silhouette de 0,89 que era un
> artefacto. Aquí usamos solo Energía TUSD en kWh, que es el consumo. Energía TE es
> el mismo kWh y sumarla lo duplicaría.
>
> Después de filtrar mercado Regular y CATIVO, agregamos por segmento y mes.
> Exigimos 95 % de cobertura. Quedan 700 segmentos, 101 distribuidoras, 99,4 % del
> consumo. Excluimos 2026-09 porque el corte de datos lo deja parcial.”

**Slide 4:** tabla de unidades de `VlrMercado`, embudo, cobertura.

**Números que hay que decir de memoria:** 6.671.150 filas · 700 unidades · 68
meses · 99,4 %.

---

## 5:00–7:00 · Diseño de experimentos

> “La crítica de los nueve escenarios era correcta. Diseñamos un factorial de 504
> corridas: 18 pipelines de representación y escalado, por 4 algoritmos, por k de 2
> a 8. Las representaciones son serie completa de 68 meses, perfil estacional de
> 12, 19 descriptores y PCA. Los algoritmos son KMeans, Ward, Average y Complete.
>
> Para comparar de forma justa, cada partición se evalúa en su propio espacio y en
> un espacio de referencia común de 68 meses. Si solo midiéramos en 2 dimensiones,
> PCA ganaría por geometría, no por calidad. También medimos estabilidad:
> reentrenamos con 80 % de los datos y medimos el acuerdo con ARI.
>
> La selección no es el máximo silhouette. Es un score multicriterio: 35 %
> separación, 25 % estabilidad, 15 % Davies–Bouldin, 10 % Calinski, 10 % balance y
> 5 % parsimonia. Descartamos k=2 porque no permite distinguir contracción de
> estabilidad y crecimiento.”

**Slide 5:** matriz 18 × 4 × 7 = 504; métricas; criterio de selección.

**Si preguntan “¿por qué no probaron más algoritmos?”:** “Probamos las dos familias
relevantes para este problema, particional y jerárquica, con cuatro criterios de
enlace. Añadir DBSCAN o mezclas gaussianas es trabajo futuro; no cambiaría la
conclusión sobre representación.”

---

## 7:00–9:30 · Resultados

> “El modelo final es serie de 68 meses, winsorizado y estandarizado por fila,
> KMeans con k=3. Silhouette 0,26, estabilidad 0,883 con 100 submuestras.
>
> Tres arquetipos. Contracción sostenida: 366 segmentos, 39,7 % del consumo,
> tendencia menos 1,1 % mensual, caída de 43 % en 12 meses. Base estable: 187
> segmentos, 44,7 % del consumo, tendencia cercana a cero, alta persistencia.
> Crecimiento acelerado: 147 segmentos, 15,6 %, crecimiento 38 %, iluminación
> pública y poder público.
>
> La separación es de trayectoria: los descriptores de tendencia, crecimiento y
> drawdown tienen los mayores tamaños de efecto, y todos sobreviven a corrección
> FDR.
>
> ¿Es solo la clase de consumo? Cramér's V 0,57, pero al quitar el efecto medio de
> la clase baja a 0,195 y el ARI entre particiones es 0,333. Hay estructura propia,
> y lo declaramos como límite.
>
> ¿La contracción es real? El cativo cae 12,8 %, el libre crece 33 % y la GD se
> multiplica por 8,7. Es consistente con migración, no con un error de datos.”

**Slide 6:** centroides de los tres arquetipos.
**Slide 7:** tabla de arquetipos + composición por clase.
**Slide 8:** mercado cativo/libre/GD.

No leer la tabla: señalar la forma de las curvas.

---

## 9:30–11:00 · Decisión y exposición

> “El resultado se traduce en una matriz de decisión. Contracción: prioridad alta,
> revisar precio y contrato, riesgo de fuga al libre. Base estable: mantener y
> monitorear cambios de régimen. Crecimiento: asegurar capacidad y revisar
> proyección.
>
> A nivel de distribuidora, 36 tienen la contracción como grupo dominante. Las
> cinco mayores tienen entre 30 y 48 % de su consumo en contracción. Ese es el
> tablero que usa un analista: no ‘hay tres grupos’, sino ‘esta distribuidora tiene
> este porcentaje de su cativo en riesgo, en estas clases’.”

**Slide 9:** matriz de decisión.
**Slide 10:** tabla/heatmap de exposición por distribuidora.

---

## 11:00–12:00 · Límites y cierre

> “Tres límites. Primero, medimos consumo facturado en el cativo, no consumo
> físico: una caída puede ser migración al libre. Segundo, la clase explica parte
> de la estructura. Tercero, la validación es por remuestreo de unidades; falta
> validación temporal hacia adelante, que es el siguiente paso.
>
> Lo que queda demostrado es: la unidad es clara y accionable, el experimento es
> amplio y reproducible, los arquetipos son estables y significativos, y la lectura
> es coherente con el mercado. Gracias.”

**Slide 11:** límites + trabajo futuro.
**Slide 12:** “Gracias / preguntas”.

---

## Preguntas difíciles y respuestas cortas

| Pregunta | Respuesta |
|---|---|
| “¿Por qué 700 y no 833?” | 99 son clases no atendidas; 34 no llegan a 95 % de cobertura. Queda 99,4 % del consumo. |
| “¿Por qué k=3 y no k=2, que tiene mejor silhouette?” | k=2 solo separa alto/bajo; no distingue contracción, estabilidad y crecimiento. El score penaliza k<3 por diseño. |
| “¿No es arbitrario el score?” | Los pesos son una preferencia declarada. El ranking completo está publicado y se recalcula cambiando pesos. |
| “¿Por qué no usaron todo 2021-2026 incluyendo septiembre?” | Septiembre 2026 está parcializado por el corte: 2,4 TWh vs ~20 TWh. Incluirlo crea una caída artificial. |
| “¿Los clústeres no son solo la clase?” | V=0,57, pero ajustando por clase baja a 0,195 y ARI=0,333. Hay estructura residual; es una limitación, no una identidad. |
| “¿Por qué no validaron con datos futuros?” | Limitación declarada. La ventana termina en 2026-08; el backtesting es trabajo futuro. |
| “¿Orange es parte del resultado?” | No. Es verificación visual independiente. El resultado se produce en Python y se registra en MLflow. La réplica sobre el CSV exportado da ARI = 1,0; eso valida la exportación, no un algoritmo distinto. |
| “¿Cómo sé que no hay fuga de información?” | El clustering no usa la etiqueta ni la clase como feature. La clase solo se usa para validar después. |
| “¿Qué pasa si cambia el precio?” | El arquetipo describe consumo, no precio. Un cambio de precio puede mover la migración; por eso la decisión es de seguimiento, no una predicción. |
| “¿Cuál es el aporte científico?” | Un marco reproducible de clustering de series regulatorias a nivel segmento, con DoE amplio, espacio común de comparación y validación estadística. |

---

## Frases que no se deben decir

- “El silhouette de 0,89 demuestra que los grupos son perfectos.” → Era un
  artefacto por sumar unidades incompatibles.
- “Elegimos k=3 porque fue el mejor.” → Se eligió por un criterio multicriterio;
  el mejor silhouette era k=2.
- “Los clústeres son independientes de la clase.” → No: hay asociación; se declara.
- “Esto predice la demanda.” → No: describe arquetipos históricos. La predicción es
  trabajo futuro.
- “Los datos son de consumidores.” → Son segmentos agregados por distribuidora y
  clase.

---

## Checklist de última hora

- [ ] `reports/tables/final_resumen.json` abierto por si piden un número exacto.
- [ ] `reports/figures/08_centroides.png` y `13_mercado...png` listas.
- [ ] Notebook 04 ejecutado (no abrir uno vacío).
- [ ] `reports/html/04_resultados_y_decision.html` abierto como respaldo si falla Jupyter.
- [ ] `reports/tables/orange_verificacion.json` a mano (ARI = 1,0) por si preguntan por Orange.
- [ ] `mlflow ui` probado antes de la sesión.
- [ ] Tener a mano la tabla de 504 corridas y el ranking.
- [ ] Saber de memoria: 700 unidades, 68 meses, 504 corridas, 0,883 estabilidad,
      −12,8 % cativo.
- [ ] Cerrar siempre con los tres límites: cativo facturado, clase parcial,
      validación temporal pendiente.
