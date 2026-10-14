# 1. Proyecto de Power BI en formato PBIP, con el modelo en TMDL

## Contexto

Un `.pbix` es un binario: en Git no se ve qué cambia, no se puede revisar una medida en una *pull request* y dos
cambios a la vez no se pueden fusionar. Para un proyecto de portfolio, además, quien lo mira en GitHub no tiene por qué
tener Power BI Desktop.

## Decisión

- Formato **PBIP**: el modelo semántico en **TMDL** (texto, una tabla por fichero, con las medidas, las relaciones,
  el grupo de cálculo y el rol de seguridad legibles) y el informe en **PBIR** (JSON por página).
- Los datos no van en el repositorio: Power Query lee los Parquet de una carpeta que es un parámetro
  (`CarpetaDeDatos`). Los Parquet se publican como *release*.
- La caché del modelo (`cache.abf`) y los ajustes locales de Desktop quedan fuera de Git.
- La CI valida el TMDL con la biblioteca oficial de Microsoft (TOM) y unas reglas propias, y los ficheros del informe
  contra los esquemas JSON publicados por Microsoft. Ninguna de las dos cosas necesita Power BI.

## Consecuencias

- El DAX se lee y se revisa en GitHub como cualquier código.
- Las páginas visuales se montan en Desktop (no tiene sentido escribir a mano el JSON de cada visual); la
  especificación de qué va en cada página está en `docs/especificacion-del-informe.md`.
