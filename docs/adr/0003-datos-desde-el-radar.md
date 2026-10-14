# 3. Los datos salen de la base del radar, exportados a Parquet con DuckDB

## Contexto

Los datos son los de la Plataforma de Contratación del Sector Público: paquetes mensuales de ficheros ATOM con el
formato CODICE, que el [radar de licitaciones](https://github.com/marnau74/radar-licitaciones) ya sabe leer,
deduplicar (cada licitación se publica de nuevo con cada cambio) y guardar en PostgreSQL.

## Decisión

- El radar carga los paquetes de enero a septiembre de 2026 y `preparar/exportar.py` lee su base con DuckDB
  (extensión de PostgreSQL) y escribe el modelo en estrella en Parquet.
- La transformación es **SQL** (`preparar/modelo.sql`): la misma consulta se prueba sobre una base en miniatura con
  el mismo esquema, con casos difíciles a propósito (lotes, códigos desconocidos, territorio solo de comunidad,
  importes absurdos).
- La exportación **se para si el modelo no está bien**: claves únicas, ninguna clave de hecho sin su dimensión,
  importes no negativos y el mismo número de licitaciones por mes que en la base. Un Parquet con errores no llega a
  Power BI.
- Las cifras de control se calculan con DuckDB sobre esos Parquet y con las mismas definiciones que las medidas DAX.

## Alternativas descartadas

- **Power Query contra la base del radar**: obliga a tener el radar en marcha para refrescar el informe y esconde la
  lógica en M, sin pruebas.
- **Leer los ATOM desde Power Query**: CODICE es un XML con espacios de nombres y versiones de cada licitación
  repetidas; reimplementar ahí lo que el radar ya hace y prueba no aporta nada.
