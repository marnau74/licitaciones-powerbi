# Especificación del informe

Cómo montar las cinco páginas en Power BI Desktop sobre el modelo ya hecho. El proyecto trae las páginas creadas y
vacías, el tema aplicado y todas las medidas; aquí se dice qué visual va en cada sitio y con qué campos. Lienzo de
1280 × 720, márgenes de 24 px y 16 px entre visuales.

Reglas para todo el informe:

- **Solo medidas explícitas** (la carpeta `Medidas`); el modelo no deja arrastrar columnas numéricas.
- Títulos de visual en frase normal («Importe licitado por mes», no «IMPORTE LICITADO POR MES») y sin
  repetir lo que ya dice el eje.
- Sin bordes ni sombras (los quita el tema). Fondo de página gris claro y visuales en blanco.
- Euros sin decimales en tarjetas y ejes; porcentajes con un decimal.
- **Segmentadores sincronizados** en todas las páginas: Mes (`Fecha[Mes y año]`), Comunidad
  (`Territorio[Comunidad]`) y Tipo de contrato (`'Tipo de contrato'[Tipo de contrato]`). Panel de sincronización: los
  tres sincronizados y visibles en todas las páginas salvo «Detalle», donde se sincronizan pero se ocultan.
- **Marcadores** «Obras», «Servicios» y «Suministros» que fijan el segmentador de tipo de contrato, más «Todo», en
  tres botones arriba a la derecha de «Resumen».
- **Accesibilidad**: texto alternativo en cada visual (qué enseña y la conclusión), orden de tabulación de arriba abajo
  y de izquierda a derecha, y no usar solo el color para distinguir series (etiquetas de datos donde haya dos colores).

## 1. Resumen

| Zona | Visual | Campos |
|---|---|---|
| Fila superior | 4 tarjetas | `[Licitaciones]`, `[Importe licitado]`, `[% de baja]`, `[Ofertas por adjudicación]` |
| Centro izquierda | Gráfico de columnas | Eje `Fecha[Mes y año]`; valor `[Importe licitado]`; línea con `[Licitaciones]` en eje secundario (gráfico combinado) |
| Centro derecha | Mapa de formas (o coroplético) | Ubicación `Territorio[Comunidad]` (o `Territorio[Código ISO]` con el mapa de España); saturación `[Importe licitado]` |
| Abajo | Matriz pequeña | Filas `'Tipo de contrato'[Tipo de contrato]`; valores `[Licitaciones]`, `[Importe licitado]`, `[% de baja]` |

Información sobre herramientas de página (página oculta de 320 × 240) para el mapa: `[Licitaciones]`, `[Importe
mediano]`, `[% con una sola oferta]` y `[% del importe a pymes]` de la comunidad.

## 2. Quién compra

| Zona | Visual | Campos |
|---|---|---|
| Izquierda | Barras horizontales | Eje `'Órgano'[Órgano]`; valor `[Importe licitado (top N órganos)]`; ordenado de mayor a menor |
| Encima de las barras | Segmentador de lista horizontal | `'Top N'[Top N]` (selección única, 10 por defecto) |
| Derecha arriba | Anillo | Leyenda `'Órgano'[Administración]`; valor `[Importe licitado]` |
| Derecha abajo | Árbol de descomposición | Analizar `[Importe licitado]`; explicar por `'Órgano'[Administración]`, `Territorio[Comunidad]`, `'Tipo de contrato'[Tipo de contrato]`, `Procedimiento[Procedimiento]` |

## 3. Quién gana

| Zona | Visual | Campos |
|---|---|---|
| Fila superior | 3 tarjetas | `[Adjudicatarios distintos]`, `[Cuota de los 10 primeros adjudicatarios]`, `[% del importe a pymes]` |
| Izquierda | Barras horizontales | Eje `Adjudicatario[Adjudicatario]`; valor `[Importe adjudicado (top N adjudicatarios)]`; segmentador de Top N como en la página 2 |
| Derecha | Columnas apiladas al 100 % | Eje `'Tipo de contrato'[Tipo de contrato]`; leyenda `Adjudicaciones[Pyme]`; valor `[Importe adjudicado]` |
| Abajo | Gráfico de líneas | Eje `Fecha[Mes y año]`; valor `[Importe adjudicado por fecha de adjudicación]` (usa la relación inactiva por fecha de adjudicación) |

## 4. Competencia

| Zona | Visual | Campos |
|---|---|---|
| Fila superior | 3 tarjetas | `[Ofertas por adjudicación]`, `[% con una sola oferta]`, `[% desiertos]` |
| Izquierda | Columnas | Eje `Adjudicaciones[Ofertas recibidas]` (de 1 a 20; filtro de visual «es menor o igual que 20»); valor `[Adjudicaciones]` |
| Derecha | Barras horizontales | Eje `Procedimiento[Procedimiento]`; valor `[% con una sola oferta]`; ordenado de mayor a menor. Se ve el negociado sin publicidad frente al abierto |
| Abajo | Dispersión | Detalles `CPV[División CPV]`; X `[Ofertas por adjudicación]`; Y `[% de baja]`; tamaño `[Importe adjudicado]`. A más competencia, más baja |

## 5. Detalle

Página de **obtención de detalles** (drill-through) con los campos `'Órgano'[Órgano]`, `Territorio[Comunidad]` y
`CPV[División CPV]`: desde cualquier visual de las otras páginas, clic derecho > Obtener detalles.

| Zona | Visual | Campos |
|---|---|---|
| Arriba | Tarjeta de varias filas | `[Licitaciones]`, `[Importe licitado]`, `[% de baja]` del contexto |
| Resto | Tabla | `Licitaciones[Número]`, `Licitaciones[Título]`, `'Órgano'[Órgano]`, `Fecha[Fecha]`, `[Importe licitado]`, `Licitaciones[URL]` (como icono de URL: formato > Valores > Iconos de URL) |

## Grupo de cálculo «Periodo»

En las tarjetas de «Resumen» se puede poner debajo una segunda tarjeta con la misma medida y el filtro de visual
`Periodo[Periodo] = Variación %` para enseñar la variación frente al mes anterior. Con un único mes elegido en el
segmentador, «Mes anterior» y «Variación» tienen sentido; con todo el periodo, «En lo que va de año».

## Seguridad por filas

Modelado > Ver como > Otro usuario: `ana@demo.example` con el rol **Comunidad** solo ve la Región de Murcia y la
Comunitat Valenciana; `admin@demo.example`, la Comunidad de Madrid. Sin rol se ve todo.
