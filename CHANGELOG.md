# Cambios

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones con
[versionado semántico](https://semver.org/lang/es/).

## [0.1.0] - 2026-10-14

Primera versión.

### Añadido

- Exportación del modelo en estrella a Parquet desde la base del radar (DuckDB), con comprobaciones que paran la
  exportación si algo falla.
- Modelo semántico en TMDL: dos tablas de hechos, ocho dimensiones, 24 medidas en carpetas, grupo de cálculo
  «Periodo», seguridad por filas por comunidad, jerarquías y tabla de fechas.
- Informe PBIR con cinco páginas y tema propio, y la especificación de los visuales de cada página.
- Validación del TMDL con TOM y reglas propias; comprobación de los ficheros del informe contra los esquemas de
  Microsoft.
- Cifras de control y comparación automática contra el motor de Power BI Desktop.
- CI escrita para GitHub Actions.
