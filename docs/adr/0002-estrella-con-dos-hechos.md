# 2. Modelo en estrella con dos tablas de hechos

## Contexto

Las preguntas del informe son de dos tipos: sobre lo que se licita (cuántas licitaciones, por qué importe, quién
compra) y sobre lo que se adjudica (quién gana, con cuánta competencia y cuánta baja). Una licitación puede tener
varios lotes y cada lote su resultado: mezclar las dos cosas en una tabla duplicaría los importes licitados.

## Decisión

- **Licitaciones**: una fila por licitación publicada en el periodo (sin las anuladas).
- **Adjudicaciones**: una fila por resultado (de la licitación o de cada lote), con el importe licitado que le
  corresponde (el del lote si lo hay) para poder calcular la baja sobre los mismos contratos.
- Dimensiones compartidas (fecha, órgano, territorio, tipo de contrato, procedimiento, CPV) con relaciones de uno a
  varios y **filtro en una sola dirección**. La fecha de adjudicación es una segunda relación con la tabla de fechas,
  **inactiva**, que se activa con `USERELATIONSHIP` en la medida que la necesita.
- Todo con **medidas explícitas** (las implícitas están desactivadas) y un **grupo de cálculo** para el mes anterior,
  la variación y el acumulado del año, en vez de repetir cada medida.

## La baja

La baja es `1 − adjudicado / licitado` como **cociente de sumas**, no como media de los porcentajes de cada contrato
(que daría el mismo peso a un contrato de mil euros que a uno de diez millones). Y solo con los resultados en los que
los dos importes existen y su proporción es creíble (entre el 5 % y el 150 %): en los datos de origen hay importes
adjudicados anuales frente a licitados totales, o con IVA frente a sin IVA, que falsearían la cifra. Cuántos se
quedan fuera se ve en las cifras de control.

## Alternativas descartadas

- **Una tabla plana**: cómoda para empezar, pero duplica importes en cuanto hay lotes y obliga a medidas con
  `DISTINCT` por todas partes.
- **Relaciones en las dos direcciones** para filtrar dimensiones por hechos: ambigüedad y resultados difíciles de
  explicar; se usa el filtro desde la dimensión, como debe ser.
