# Cifras de control

Lo que tienen que dar las medidas del modelo sin ningún filtro, calculado con DuckDB sobre los mismos Parquet
(`preparar/cifras.py`). Si una medida de Power BI no coincide, el error está en el DAX o en el modelo.

Periodo: del 2026-01-01 al 2026-09-30 (fecha de publicación). Licitaciones anuladas excluidas: 315.

| Medida | Valor esperado |
|---|---:|
| Licitaciones | 125.658 |
| Importe licitado | 73.643.923.645 € |
| Importe medio | 604.372 € |
| Importe mediano | 50.413 € |
| % con fondos UE | 7,1 % |
| Días de plazo (mediana) | 15 |
| Adjudicaciones | 110.448 |
| Importe adjudicado | 23.818.434.195 € |
| % de baja | 11,9 % |
| Ofertas por adjudicación | 3,25 |
| % con una sola oferta | 48,7 % |
| % del importe a pymes | 28,0 % |
| % desiertos | 9,2 % |
| Adjudicatarios distintos | 31.278 |
| Cuota de los 10 primeros adjudicatarios | 16,5 % |

## Licitaciones por mes de publicación

`Fecha[Mes]` con la medida `[Licitaciones]`.

| | Licitaciones |
|---|---:|
| enero | 9.281 |
| febrero | 12.832 |
| marzo | 15.365 |
| abril | 14.670 |
| mayo | 15.260 |
| junio | 16.658 |
| julio | 16.361 |
| agosto | 11.614 |
| septiembre | 13.617 |

## Licitaciones por tipo de contrato

`'Tipo de contrato'[Tipo de contrato]` con la medida `[Licitaciones]`.

| | Licitaciones |
|---|---:|
| Servicios | 48.523 |
| Suministros | 45.703 |
| Obras | 22.305 |
| Privado | 3.998 |
| Patrimonial | 2.985 |
| Concesión de Servicios | 1.648 |
| Administrativo especial | 463 |
| Concesión de Obras | 26 |
| Concesión de Obras Públicas | 3 |
| Gestión de Servicios Públicos | 3 |
| Colaboración entre el sector público y sector privado | 1 |

## Licitaciones por comunidad (las cinco con más)

`Territorio[Comunidad]` con la medida `[Licitaciones]`.

| | Licitaciones |
|---|---:|
| Comunidad de Madrid | 24.929 |
| Andalucía | 21.225 |
| Comunitat Valenciana | 14.467 |
| Castilla y León | 9.159 |
| Canarias | 8.781 |
