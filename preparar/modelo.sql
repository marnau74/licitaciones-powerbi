-- El modelo en estrella del informe, a partir de la base del radar (esquema `radar.public`).
-- Cada sentencia crea una tabla en la base de trabajo; exportar.py las escribe en Parquet.
-- Los parámetros {desde} y {hasta} delimitan el periodo por fecha de publicación.

-- Licitaciones del periodo, sin las anuladas por la Plataforma.
CREATE TABLE licitaciones AS
SELECT l.*
FROM radar.public.licitacion AS l
WHERE l.fecha_publicacion BETWEEN DATE '{desde}' AND DATE '{hasta}'
  AND NOT l.anulada;

-- Territorio: provincia (NUTS 3) con su comunidad (NUTS 2). Las licitaciones que solo indican la comunidad, las
-- que se ejecutan fuera de España y las que no lo indican tienen su propia fila, para no perderlas al filtrar.
CREATE TABLE dim_territorio AS
WITH comunidades AS (
    SELECT codigo, nombre FROM radar.public.cat_nuts WHERE nivel = 2 AND codigo NOT LIKE 'ESZ%'
),
iso (nuts, iso) AS (
    VALUES ('ES11', 'ES-GA'), ('ES12', 'ES-AS'), ('ES13', 'ES-CB'), ('ES21', 'ES-PV'), ('ES22', 'ES-NC'),
           ('ES23', 'ES-RI'), ('ES24', 'ES-AR'), ('ES30', 'ES-MD'), ('ES41', 'ES-CL'), ('ES42', 'ES-CM'),
           ('ES43', 'ES-EX'), ('ES51', 'ES-CT'), ('ES52', 'ES-VC'), ('ES53', 'ES-IB'), ('ES61', 'ES-AN'),
           ('ES62', 'ES-MC'), ('ES63', 'ES-CE'), ('ES64', 'ES-ML'), ('ES70', 'ES-CN')
)
SELECT p.codigo AS cod_territorio, p.nombre AS provincia, c.codigo AS cod_comunidad, c.nombre AS comunidad, i.iso
FROM radar.public.cat_nuts AS p
JOIN comunidades AS c ON c.codigo = left(p.codigo, 4)
JOIN iso AS i ON i.nuts = c.codigo
WHERE p.nivel = 3
UNION ALL
SELECT c.codigo, '(Toda la comunidad)', c.codigo, c.nombre, i.iso
FROM comunidades AS c
JOIN iso AS i ON i.nuts = c.codigo
UNION ALL
SELECT 'EXT', '(Fuera de España)', 'EXT', '(Fuera de España)', NULL
UNION ALL
SELECT 'ZZ', '(Sin indicar)', 'ZZ', '(Sin indicar)', NULL;

-- Catálogos. Un código que no esté en el catálogo (la Plataforma añade alguno de vez en cuando) va a «(Sin indicar)».
CREATE TABLE dim_tipo_contrato AS
SELECT codigo AS cod_tipo_contrato, nombre AS tipo_contrato FROM radar.public.cat_tipo_contrato
UNION ALL SELECT '?', '(Sin indicar)';

CREATE TABLE dim_procedimiento AS
SELECT codigo AS cod_procedimiento, nombre AS procedimiento FROM radar.public.cat_procedimiento
UNION ALL SELECT '?', '(Sin indicar)';

CREATE TABLE dim_estado AS
SELECT codigo AS cod_estado, nombre AS estado FROM radar.public.cat_estado
UNION ALL SELECT '?', '(Sin indicar)';

CREATE TABLE dim_resultado AS
SELECT codigo AS cod_resultado, nombre AS resultado FROM radar.public.cat_resultado
UNION ALL SELECT '?', '(Sin indicar)';

-- Divisiones CPV (los dos primeros dígitos): los códigos que acaban en seis ceros.
CREATE TABLE dim_cpv AS
SELECT left(codigo, 2) AS cod_cpv_division, nombre AS division_cpv
FROM radar.public.cat_cpv
WHERE codigo LIKE '__000000'
UNION ALL SELECT '??', '(Sin indicar)';

CREATE TABLE hechos_licitacion AS
SELECT
    l.id AS id_licitacion,
    l.expediente,
    l.titulo,
    l.url,
    l.fecha_publicacion,
    l.organo_id AS id_organo,
    CASE
        WHEN l.nuts IN (SELECT cod_territorio FROM dim_territorio) THEN l.nuts
        WHEN left(l.nuts, 4) IN (SELECT cod_territorio FROM dim_territorio) THEN left(l.nuts, 4)
        WHEN l.nuts IS NOT NULL AND l.nuts NOT LIKE 'ES%' THEN 'EXT'
        ELSE 'ZZ'
    END AS cod_territorio,
    CASE WHEN l.tipo_contrato IN (SELECT cod_tipo_contrato FROM dim_tipo_contrato) THEN l.tipo_contrato ELSE '?' END
        AS cod_tipo_contrato,
    CASE WHEN l.procedimiento IN (SELECT cod_procedimiento FROM dim_procedimiento) THEN l.procedimiento ELSE '?' END
        AS cod_procedimiento,
    CASE WHEN left(l.cpv[1], 2) IN (SELECT cod_cpv_division FROM dim_cpv) THEN left(l.cpv[1], 2) ELSE '??' END
        AS cod_cpv_division,
    CASE WHEN l.estado IN (SELECT cod_estado FROM dim_estado) THEN l.estado ELSE '?' END AS cod_estado,
    -- Un importe de 0 es un importe sin informar (en la Plataforma no hay licitaciones gratuitas): cuenta como vacío.
    nullif(l.importe_sin_iva, 0) AS importe_sin_iva,
    nullif(l.valor_estimado, 0) AS valor_estimado,
    l.num_lotes,
    l.financiacion_ue,
    -- Días que tuvieron las empresas para presentar oferta (nulo si no hay plazo publicado).
    CASE WHEN l.plazo_presentacion IS NOT NULL
         THEN date_diff('day', l.fecha_publicacion, CAST(l.plazo_presentacion AS DATE)) END AS dias_de_plazo
FROM licitaciones AS l;

-- Un resultado por licitación o por lote. El importe licitado comparable es el del lote si lo hay y si no el de la
-- licitación; solo se usa para la baja cuando los dos importes existen y su proporción es creíble (una parte de los
-- datos de origen mezcla importes anuales y totales, o con y sin IVA).
CREATE TABLE hechos_adjudicacion AS
WITH resultados AS (
    SELECT
        r.id,
        r.licitacion_id,
        r.lote,
        r.codigo,
        r.fecha_adjudicacion,
        r.ofertas_recibidas,
        nullif(upper(regexp_replace(coalesce(r.adjudicatario_nif, ''), '[^A-Za-z0-9]', '', 'g')), '') AS nif,
        r.importe_sin_iva AS importe_adjudicado,
        coalesce(lo.importe_sin_iva, CASE WHEN r.lote IS NULL OR l.num_lotes = 0 THEN l.importe_sin_iva END)
            AS importe_licitado,
        r.pyme
    FROM radar.public.resultado AS r
    JOIN licitaciones AS l ON l.id = r.licitacion_id
    LEFT JOIN radar.public.lote AS lo ON lo.licitacion_id = r.licitacion_id AND lo.numero = r.lote
)
SELECT
    r.id AS id_resultado,
    r.licitacion_id AS id_licitacion,
    r.lote,
    CASE WHEN r.codigo IN (SELECT cod_resultado FROM dim_resultado) THEN r.codigo ELSE '?' END AS cod_resultado,
    r.codigo IN ('1', '2', '8', '9', '11') AS adjudicado,
    r.codigo IN ('3', '6', '7') AS desierto,
    r.fecha_adjudicacion,
    h.fecha_publicacion,
    h.id_organo,
    h.cod_territorio,
    h.cod_tipo_contrato,
    h.cod_procedimiento,
    h.cod_cpv_division,
    coalesce(r.nif, 'SIN-NIF') AS nif_adjudicatario,
    r.ofertas_recibidas,
    r.importe_adjudicado,
    r.importe_licitado,
    r.importe_adjudicado > 0 AND r.importe_licitado > 0
        AND r.importe_adjudicado / r.importe_licitado BETWEEN 0.05 AND 1.5 AS importe_comparable,
    r.pyme
FROM resultados AS r
JOIN hechos_licitacion AS h ON h.id_licitacion = r.licitacion_id;

CREATE TABLE dim_fecha AS
SELECT
    CAST(d AS DATE) AS fecha,
    year(d) AS anio,
    quarter(d) AS trimestre,
    month(d) AS mes,
    ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
     'noviembre', 'diciembre'][month(d)] AS nombre_mes,
    ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][month(d)]
        || ' ' || year(d) AS mes_anio,
    year(d) * 100 + month(d) AS orden_mes_anio,
    isodow(d) AS dia_semana,
    ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][isodow(d)] AS nombre_dia
FROM generate_series(TIMESTAMP '{anio}-01-01', TIMESTAMP '{anio}-12-31', INTERVAL 1 DAY) AS t(d);

CREATE TABLE dim_organo AS
SELECT
    o.id AS id_organo,
    o.nombre AS organo,
    o.nif,
    o.dir3,
    o.ciudad,
    coalesce(t.nombre, '(Sin indicar)') AS tipo_organo,
    CASE
        WHEN o.tipo IN ('1', '6', '9') THEN 'Estatal'
        WHEN o.tipo IN ('2', '7', '10') THEN 'Autonómica'
        WHEN o.tipo IN ('3', '8', '11') THEN 'Local'
        ELSE 'Otras entidades'
    END AS administracion
FROM radar.public.organo AS o
LEFT JOIN radar.public.cat_tipo_organo AS t ON t.codigo = o.tipo
WHERE o.id IN (SELECT id_organo FROM hechos_licitacion);

-- Adjudicatarios agrupados por NIF, con el nombre con el que más veces aparecen.
CREATE TABLE dim_adjudicatario AS
WITH nombres AS (
    SELECT
        coalesce(nullif(upper(regexp_replace(coalesce(r.adjudicatario_nif, ''), '[^A-Za-z0-9]', '', 'g')), ''),
                 'SIN-NIF') AS nif,
        r.adjudicatario AS nombre,
        r.pyme
    FROM radar.public.resultado AS r
    WHERE r.id IN (SELECT id_resultado FROM hechos_adjudicacion)
)
SELECT
    nif AS nif_adjudicatario,
    CASE WHEN nif = 'SIN-NIF' THEN '(Sin NIF)' ELSE mode(nombre) END AS adjudicatario,
    coalesce(bool_or(pyme), false) AS pyme
FROM nombres
GROUP BY nif;
