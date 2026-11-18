# Diccionario de datos y decisiones de limpieza

**Proyecto:** arquetipos de consumo eléctrico del mercado cativo (ANEEL/SAMP)
**Fuente:** datos abiertos del *Sistema de Acompanhamento do Mercado de Energia
Elétrica* (SAMP), ANEEL.
**Corte de generación:** 2026-10-15 (`DatGeracaoConjuntoDados`).

---

## 1. Archivo crudo

6 CSV anuales (`samp-2021.csv` … `samp-2026.csv`), separador `;`, codificación
`latin1`, 18 columnas y **6.671.150 filas**.

| # | Columna | Tipo | Ejemplo | Uso en el proyecto |
|---|---|---|---|---|
| 1 | `DatGeracaoConjuntoDados` | fecha | 2026-10-15 | control de versión del corte |
| 2 | `NumCNPJAgenteDistribuidora` | texto | 05914650000166 | identificación legal |
| 3 | `SigAgenteDistribuidora` | texto | ERO | **clave de unidad** |
| 4 | `NomAgenteDistribuidora` | texto | ENERGISA RONDONIA… | nombre legible |
| 5 | `NomTipoMercado` | texto | Regular | **filtro** |
| 6 | `DscModalidadeTarifaria` | texto | Convencional | contexto tarifario |
| 7 | `DscSubGrupoTarifario` | texto | B2 | contexto tarifario |
| 8 | `DscClasseConsumoMercado` | texto | Rural | **clave de unidad / clase** |
| 9 | `DscSubClasseConsumidor` | texto | Não se aplica | no usado |
| 10 | `DscDetalheConsumidor` | texto | Não se aplica | no usado |
| 11 | `IdeNucleoCeg` | texto | 0 | no usado |
| 12 | `NumCNPJAgenteAcessante` | texto | 37121669900 | no usado |
| 13 | `NomAgenteAcessante` | texto | Não se aplica | no usado |
| 14 | `DscPostoTarifario` | texto | Não se aplica | no usado |
| 15 | `DscOpcaoEnergia` | texto | CATIVO | **filtro** |
| 16 | `DscDetalheMercado` | texto | Número de consumidores | **selector de variable** |
| 17 | `DatCompetencia` | fecha | 2021-10-01 | **eje temporal** |
| 18 | `VlrMercado` | texto numérico | 100249,000000 | **valor** |

Cada fila cruda es una celda de un cubo: distribuidora × clase × tipo de mercado
× opción de energía × detalle × mes. **No es un consumidor ni una observación
independiente.**

---

## 2. El problema de `VlrMercado`

`VlrMercado` es un contenedor genérico. Su unidad la define
`DscDetalheMercado`:

| Detalle (ejemplos) | Unidad | Uso |
|---|---|---|
| `Energia TUSD (kWh)` | kWh | **variable de consumo del proyecto** |
| `Energia TE (kWh)` | kWh | mismo kWh que TUSD; **no sumar** |
| `Receita Energia (R$)`, `ICMS (R$)`, `PIS/PASEP (R$)`, `COFINS (R$)` | R$ | contexto monetario |
| `Demanda Faturada (kW)`, `Demanda Contratada kW`, `Ultrapassagem Demanda (kW)` | kW | contexto de potencia |
| `Desconto Demanda %`, `Desconto de energia compensada %` | % | excluido |
| `Número de consumidores`, `Número de Consumidores` | conteo | contexto / filtro de tamaño |

**Decisión.** Para consumo se usa **solo** `Energia TUSD (kWh)`. Sumar TE y TUSD
duplica el kWh; sumar R$, kW, % y conteos produce un número sin unidad.

### 2.1 Detalle sensible a mayúsculas

ANEEL publica dos etiquetas casi idénticas:

- `Número de consumidores` (minúscula): usada por el mercado **CATIVO**.
- `Número de Consumidores` (mayúscula): usada por **LIVRE, GERAÇÃO,
  DISTRIBUIÇÃO, SUPRIMENTO** y por la clase `Não se aplica`.

Normalizar todo a minúsculas mezclaría universos distintos y duplicaría el conteo
de consumidores. Por eso el pipeline **no** normaliza `DscDetalheMercado`; filtra
primero `Regular + CATIVO` y luego busca la etiqueta exacta.

---

## 3. Filtros aplicados (en orden)

| Paso | Regla | Filas resultantes |
|---|---|---:|
| 0 | Leer 6 CSV | 6.671.150 |
| 1 | `NomTipoMercado == "Regular"` | — |
| 2 | `DscOpcaoEnergia == "CATIVO"` | 2.116.425 |
| 3 | `DscDetalheMercado == "Energia TUSD (kWh)"` | 302.717 |
| 4 | Agregar por distribuidora × clase × mes | 55.140 celdas de panel |
| 5 | Conservar 7 clases de mercado | 734 unidades |
| 6 | Cobertura ≥ 95 % y huecos imputables ≤ 2 meses | **700 unidades** |
| 7 | Ventana 2021-01 … 2026-08 | 68 meses |

**Por qué se excluyen otros tipos de mercado**

- `Refaturamento - Regular`: ajustes contables, no consumo del período.
- `Sistema de Compensação GD I/II/III`: generación distribuida; se analiza aparte
  como contexto, no como consumo cativo.
- `Sistema Isolado / Individual`: mercados no conectados a la red de distribución.
- `RTE`: registro de transacciones especiales.

**Por qué se excluye 2026-09**

El corte del 2026-10-15 deja septiembre con 2,4 TWh frente a ~20 TWh de un mes
completo (22.741 filas frente a ~121.000). Incluirlo introduciría una caída
artificial al final de todas las series.

---

## 4. Clases de consumo

Se conservan 7 clases que representan mercado atendido:

```
Residencial, Comercial, Industrial, Rural,
Poder público, Iluminação pública, Serviço público
```

Se excluyen:

- `Não se aplica`: agregados administrativos sin clase.
- `Consumo próprio`: energía consumida por la propia distribuidora, no mercado
  atendido.

Se unifica `Serviço Público` → `Serviço público` (diferencia de capitalización).

---

## 5. Panel procesado (`data/processed/painel_mensal.csv`)

| Columna | Unidad | Descripción |
|---|---|---|
| `unidad` | texto | `agente \| clase` |
| `agente` | texto | `SigAgenteDistribuidora` |
| `clase` | texto | clase de consumo normalizada |
| `mes` | `YYYY-MM` | mes de competencia |
| `consumo_mwh` | MWh | suma de `Energia TUSD (kWh)` / 1000 |
| `n_consumidores` | conteo | `Número de consumidores` (solo cativo) |

**Calidad del panel**

- 55.140 filas, 833 unidades, 105 agentes, 2021-01 a 2026-09.
- 0 valores negativos de energía (los 664.448 negativos del crudo están en R$).
- 3 valores nulos de consumo (se resuelven o excluyen en la matriz).
- 1.603,3 TWh totales; 1.587,2 TWh en las 700 unidades incluidas.

---

## 6. Matrices y features

### 6.1 `matriz_serie68_mwh.csv`

700 filas × 68 columnas (`2021-01` … `2026-08`), valores en MWh. Huecos internos
de hasta 2 meses interpolados linealmente; si queda un NaN, la unidad se excluye.

### 6.2 `matriz_estacional12_mwh.csv`

700 filas × 12 columnas (`M01` … `M12`): promedio de cada mes calendario. Captura
estacionalidad, pierde evolución.

### 6.3 `descriptores.csv`

19 descriptores de forma + metadatos de tamaño. Definiciones (sea $y_t$ la serie
de la unidad, $\bar y$ su media, $T=68$):

| Descriptor | Fórmula / definición | Interpretación |
|---|---|---|
| `cv` | $\sigma(y)/\bar y$ | volatilidad relativa |
| `tendencia_pct_mes` | $\hat\beta_{OLS}/\bar y \times 100$ | cambio porcentual mensual |
| `tendencia_r2` | $R^2$ de la regresión lineal | fuerza de la tendencia |
| `amplitud_estacional` | $(\max_m \bar y_m - \min_m \bar y_m)/\bar y$ | rango estacional relativo |
| `fuerza_estacionalidad` | $\mathrm{Var}(\hat y^{est}_t)/\mathrm{Var}(y_t)$ | cuánto explica la estacionalidad |
| `ac1` | correlación $y_t, y_{t-1}$ | persistencia mensual |
| `ac12` | correlación $y_t, y_{t-12}$ | persistencia anual |
| `yoy_media` | media de $y_t/y_{t-12}-1$ | crecimiento año contra año |
| `yoy_std` | desviación de esa serie | inestabilidad del crecimiento |
| `drawdown_max` | $\max_t (1-y_t/\max_{s\le t} y_s)$ | mayor caída desde un máximo |
| `rango_p90_p10` | $(P_{90}-P_{10})/\bar y$ | dispersión robusta |
| `iqr_relativo` | $(P_{75}-P_{25})/\bar y$ | dispersión robusta |
| `share_bajo_80` | fracción de meses con $y_t<0{,}8\bar y$ | tiempo en valle |
| `share_alto_120` | fracción de meses con $y_t>1{,}2\bar y$ | tiempo en pico |
| `crecimiento_12m` | $\overline{y}_{[T-11,T]}/\overline{y}_{[1,12]}-1$ | cambio de régimen |
| `pico_sin`, `pico_cos` | $\sin/\cos(2\pi(m_{pico}-1)/12)$ | mes de máximo, circular |
| `valle_sin`, `valle_cos` | idem para el mínimo | mes de mínimo, circular |
| `total_mwh` | suma de la serie | tamaño (no entra al clustering) |
| `consumidores_medios` | promedio mensual | tamaño de base (no entra) |

**Por qué el tamaño queda fuera del clustering.** Si `total_mwh` entrara, KMeans
separaría grandes de pequeños y el resultado no describiría comportamiento. El
tamaño se usa después para ponderar el impacto económico de cada arquetipo.

### 6.4 PCA

`pca_serie68.csv`: 10 componentes sobre la serie estandarizada por fila.
`pca_varianza.csv`: varianza explicada y acumulada.
`pca_estacional12.csv`: 6 componentes sobre el perfil estacional.

---

## 7. Reglas de calidad y trazabilidad

1. **Parseo brasileño:** los valores usan coma decimal y punto de miles
   (`1.234,56`). `parse_br` elimina puntos solo si hay coma.
2. **Formato inválido:** 54.767 celdas (0,8 %) no son numéricas y se convierten en
   NaN; no se imputan a nivel crudo.
3. **Duplicados:** se agregan con `sum` por distribuidora × clase × mes; no se
   eliminan filas a ciegas.
4. **Negativos:** se conservan en R$ (ajustes), pero se verifica que energía no
   tenga negativos (0 casos).
5. **Cobertura:** se mide antes de imputar; el umbral es 95 % de 68 meses.
6. **Ventana:** se recorta después de construir el panel para no perder meses
   anteriores al inicio del análisis.
7. **Semilla:** 42 para KMeans, PCA, submuestreo y figuras.
8. **Versionado:** cada corrida registra parámetros, métricas y etiquetas en
   MLflow (`mlflow.db`).
