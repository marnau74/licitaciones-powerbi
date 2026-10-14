"""La exportación sobre una base del radar en miniatura (DuckDB en memoria con el mismo esquema que PostgreSQL)."""

from datetime import date

import duckdb
import pytest

from preparar.exportar import ModeloNoValido, Periodo, comprobar, construir, exportar

PERIODO = Periodo(date(2026, 1, 1), date(2026, 9, 30))

ESQUEMA = """
ATTACH ':memory:' AS radar;
CREATE SCHEMA radar.public;
CREATE TABLE radar.public.cat_tipo_contrato (codigo text PRIMARY KEY, nombre text);
CREATE TABLE radar.public.cat_procedimiento (codigo text PRIMARY KEY, nombre text);
CREATE TABLE radar.public.cat_estado (codigo text PRIMARY KEY, nombre text);
CREATE TABLE radar.public.cat_resultado (codigo text PRIMARY KEY, nombre text);
CREATE TABLE radar.public.cat_tipo_organo (codigo text PRIMARY KEY, nombre text);
CREATE TABLE radar.public.cat_nuts (codigo text PRIMARY KEY, nombre text, nivel smallint);
CREATE TABLE radar.public.cat_cpv (codigo text PRIMARY KEY, nombre text);
CREATE TABLE radar.public.organo (id bigint PRIMARY KEY, nombre text, nif text, dir3 text, tipo text, ciudad text);
CREATE TABLE radar.public.licitacion (
    id bigint PRIMARY KEY, expediente text, titulo text, url text, estado text, tipo_contrato text,
    procedimiento text, organo_id bigint, importe_sin_iva decimal(18, 2), valor_estimado decimal(18, 2),
    cpv text[], nuts text, plazo_presentacion timestamptz, fecha_publicacion date, financiacion_ue boolean,
    num_lotes smallint, anulada boolean);
CREATE TABLE radar.public.lote (licitacion_id bigint, numero text, importe_sin_iva decimal(18, 2));
CREATE TABLE radar.public.resultado (
    id bigint PRIMARY KEY, licitacion_id bigint, lote text, codigo text, fecha_adjudicacion date,
    ofertas_recibidas integer, adjudicatario text, adjudicatario_nif text, importe_sin_iva decimal(18, 2),
    pyme boolean);

INSERT INTO radar.public.cat_tipo_contrato VALUES ('1', 'Suministros'), ('2', 'Servicios'), ('3', 'Obras');
INSERT INTO radar.public.cat_procedimiento VALUES ('1', 'Abierto'), ('9', 'Abierto simplificado');
INSERT INTO radar.public.cat_estado VALUES ('PUB', 'Publicada'), ('RES', 'Resuelta');
INSERT INTO radar.public.cat_resultado VALUES ('3', 'Desierto'), ('8', 'Adjudicado'), ('9', 'Formalizado');
INSERT INTO radar.public.cat_tipo_organo VALUES ('1', 'Autoridad estatal'), ('3', 'Autoridad local');
INSERT INTO radar.public.cat_nuts VALUES
    ('ES', 'España', 0), ('ES6', 'Sur', 1), ('ES62', 'Región de Murcia', 2), ('ES620', 'Murcia', 3),
    ('ES61', 'Andalucía', 2), ('ES612', 'Cádiz', 3), ('ESZZ', 'Extra-Regio NUTS 2', 2);
INSERT INTO radar.public.cat_cpv VALUES
    ('45000000', 'Trabajos de construcción'), ('72000000', 'Servicios TI'), ('72200000', 'Programación');
INSERT INTO radar.public.organo VALUES
    (1, 'Ayuntamiento de Murcia', 'P3003000A', 'L01300308', '3', 'Murcia'),
    (2, 'Ministerio de Ejemplo', 'S2800000A', NULL, '1', 'Madrid'),
    (3, 'Órgano sin licitaciones del periodo', NULL, NULL, NULL, NULL);

INSERT INTO radar.public.licitacion VALUES
    -- Obra en Murcia con dos lotes, adjudicados.
    (10, 'E-10', 'Obra', 'https://x/10', 'RES', '3', '1', 1, 200000, 220000, ['45000000'], 'ES620',
     '2026-02-01 13:00:00+00', DATE '2026-01-10', false, 2, false),
    -- Servicio de TI con la comunidad solo, sin lotes, adjudicado a una pyme.
    (11, 'E-11', 'TI', NULL, 'RES', '2', '9', 2, 50000, 50000, ['72200000', '45000000'], 'ES62',
     NULL, DATE '2026-03-05', true, 0, false),
    -- Sin territorio ni CPV ni tipo, con un código de procedimiento que no está en el catálogo.
    (12, 'E-12', 'Raro', NULL, 'PUB', NULL, '99', 2, NULL, NULL, [], NULL, NULL, DATE '2026-09-30', false, 0, false),
    -- Fuera del periodo y anulada: no entran.
    (13, 'E-13', 'De 2025', NULL, 'PUB', '1', '1', 2, 1000, NULL, [], 'ES612', NULL, DATE '2025-12-31', false, 0,
     false),
    (14, 'E-14', 'Anulada', NULL, 'PUB', '1', '1', 1, 1000, NULL, [], 'ES612', NULL, DATE '2026-04-01', false, 0, true),
    -- Se ejecuta fuera de España.
    (15, 'E-15', 'Fuera', NULL, 'PUB', '2', '1', 1, 0, NULL, [], 'FR101', NULL, DATE '2026-05-20', false, 0, false);

INSERT INTO radar.public.lote VALUES (10, '1', 120000), (10, '2', 80000);

INSERT INTO radar.public.resultado VALUES
    (100, 10, '1', '9', DATE '2026-03-01', 4, 'CONSTRUCCIONES PÉREZ SL', 'B-12345678', 96000, false),
    (101, 10, '2', '9', DATE '2026-03-01', 1, 'Construcciones Pérez, S.L.', 'b12345678', 80000, false),
    (102, 11, NULL, '8', DATE '2026-04-10', 2, 'Software Murcia SL', 'B87654321', 40000, true),
    -- Importe adjudicado absurdo (diez veces el licitado): no cuenta para la baja.
    (103, 11, NULL, '8', DATE '2026-04-11', 3, 'Software Murcia SL', 'B87654321', 500000, true),
    (104, 12, NULL, '3', NULL, 0, NULL, NULL, NULL, NULL),
    -- Resultado de una licitación fuera del periodo: no entra.
    (105, 13, NULL, '8', DATE '2026-01-05', 1, 'Otra', 'A11111111', 900, false);
"""


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect()
    conexion.execute(ESQUEMA)
    construir(conexion, PERIODO)
    return conexion


def filas(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    return con.execute(sql).fetchall()


def test_solo_entran_las_del_periodo_y_no_anuladas(con):
    assert filas(con, "SELECT id_licitacion FROM hechos_licitacion ORDER BY 1") == [(10,), (11,), (12,), (15,)]


def test_el_modelo_supera_las_comprobaciones(con):
    assert comprobar(con, PERIODO) == []


def test_territorio_por_provincia_comunidad_extranjero_o_sin_indicar(con):
    assert dict(filas(con, "SELECT id_licitacion, cod_territorio FROM hechos_licitacion")) == {
        10: "ES620",
        11: "ES62",
        12: "ZZ",
        15: "EXT",
    }
    murcia = filas(con, "SELECT provincia, comunidad, iso FROM dim_territorio WHERE cod_territorio = 'ES620'")
    assert murcia == [("Murcia", "Región de Murcia", "ES-MC")]
    assert filas(con, "SELECT count(*) FROM dim_territorio WHERE cod_territorio LIKE 'ESZ%'") == [(0,)]


def test_codigos_desconocidos_van_a_sin_indicar(con):
    fila = filas(
        con,
        "SELECT cod_tipo_contrato, cod_procedimiento, cod_cpv_division FROM hechos_licitacion WHERE id_licitacion = 12",
    )
    assert fila == [("?", "?", "??")]


def test_la_division_cpv_es_la_del_primer_codigo(con):
    assert filas(con, "SELECT cod_cpv_division FROM hechos_licitacion WHERE id_licitacion = 11") == [("72",)]


def test_un_importe_cero_es_un_importe_sin_informar(con):
    assert filas(con, "SELECT importe_sin_iva FROM hechos_licitacion WHERE id_licitacion = 15") == [(None,)]


def test_dias_de_plazo(con):
    assert filas(con, "SELECT dias_de_plazo FROM hechos_licitacion WHERE id_licitacion = 10") == [(22,)]


def test_un_plazo_anterior_a_la_publicacion_o_de_mas_de_un_anio_no_cuenta():
    conexion = duckdb.connect()
    conexion.execute(ESQUEMA)
    conexion.execute(
        """UPDATE radar.public.licitacion SET plazo_presentacion = CASE id
               WHEN 11 THEN TIMESTAMPTZ '2026-01-05 13:00:00+00'
               WHEN 12 THEN TIMESTAMPTZ '2028-01-01 13:00:00+00' END
           WHERE id IN (11, 12)"""
    )
    construir(conexion, PERIODO)
    assert filas(conexion, "SELECT dias_de_plazo FROM hechos_licitacion WHERE id_licitacion IN (11, 12)") == [
        (None,),
        (None,),
    ]


def test_importe_licitado_del_lote_o_de_la_licitacion(con):
    assert dict(filas(con, "SELECT id_resultado, importe_licitado FROM hechos_adjudicacion")) == {
        100: 120000,
        101: 80000,
        102: 50000,
        103: 50000,
        104: None,
    }


def test_solo_los_importes_creibles_cuentan_para_la_baja(con):
    comparables = filas(con, "SELECT id_resultado FROM hechos_adjudicacion WHERE importe_comparable ORDER BY 1")
    assert comparables == [(100,), (101,), (102,)]


def test_adjudicatarios_agrupados_por_nif_normalizado(con):
    assert filas(con, "SELECT DISTINCT nif_adjudicatario FROM hechos_adjudicacion ORDER BY 1") == [
        ("B12345678",),
        ("B87654321",),
        ("SIN-NIF",),
    ]
    pyme = filas(con, "SELECT pyme FROM dim_adjudicatario WHERE nif_adjudicatario = 'B87654321'")
    assert pyme == [(True,)]


def test_las_personas_fisicas_no_salen_con_su_nombre_ni_su_dni():
    conexion = duckdb.connect()
    conexion.execute(ESQUEMA)
    conexion.execute(
        """INSERT INTO radar.public.resultado VALUES
        (106, 11, NULL, '8', DATE '2026-04-12', 1, 'Ana Martínez López', '12345678-Z', 30000, true),
        (107, 11, NULL, '8', DATE '2026-04-13', 1, 'Ana Martínez López', 'X1234567L', 20000, true)"""
    )
    construir(conexion, PERIODO)

    personas = filas(
        conexion, "SELECT nif_adjudicatario, adjudicatario FROM dim_adjudicatario WHERE nif_adjudicatario LIKE 'PF-%'"
    )
    assert len(personas) == 2
    assert all(nombre == "Persona física" for _, nombre in personas)
    volcado = str(filas(conexion, "SELECT * FROM dim_adjudicatario")) + str(
        filas(conexion, "SELECT * FROM hechos_adjudicacion")
    )
    assert "12345678Z" not in volcado and "X1234567L" not in volcado and "Martínez" not in volcado
    # El código es el mismo en las dos tablas: la relación del modelo sigue funcionando.
    assert comprobar(conexion, PERIODO) == []
    # Las empresas no cambian.
    assert filas(conexion, "SELECT adjudicatario FROM dim_adjudicatario WHERE nif_adjudicatario = 'B87654321'") == [
        ("Software Murcia SL",)
    ]


def test_con_el_nif_mal_escrito_se_protege_a_quien_no_parece_una_organizacion():
    conexion = duckdb.connect()
    conexion.execute(ESQUEMA)
    conexion.execute(
        """INSERT INTO radar.public.resultado VALUES
        (106, 11, NULL, '8', DATE '2026-04-12', 1, 'SANDRA RUBIO PÉREZ', '0002', 30000, true),
        (107, 11, NULL, '8', DATE '2026-04-13', 1, 'Rubén Llaquet Granado', '1806441B', 20000, true),
        (108, 11, NULL, '8', DATE '2026-04-14', 1, 'Hormigones del Sur, S.L.', '5740', 10000, true),
        (109, 11, NULL, '8', DATE '2026-04-15', 1, 'Elsevier B.V.', 'NL005033019B01', 5000, false)"""
    )
    construir(conexion, PERIODO)

    nombres = [nombre for (nombre,) in filas(conexion, "SELECT adjudicatario FROM dim_adjudicatario ORDER BY 1")]
    assert nombres.count("Posible persona física") == 2
    assert "Hormigones del Sur, S.L." in nombres and "Elsevier B.V." in nombres
    volcado = str(filas(conexion, "SELECT * FROM dim_adjudicatario")) + str(
        filas(conexion, "SELECT * FROM hechos_adjudicacion")
    )
    assert "RUBIO" not in volcado and "Llaquet" not in volcado and "1806441B" not in volcado
    assert comprobar(conexion, PERIODO) == []


def test_adjudicado_y_desierto(con):
    assert dict(filas(con, "SELECT id_resultado, adjudicado FROM hechos_adjudicacion"))[104] is False
    assert filas(con, "SELECT desierto FROM hechos_adjudicacion WHERE id_resultado = 104") == [(True,)]


def test_administracion_por_tipo_de_organo(con):
    assert dict(filas(con, "SELECT id_organo, administracion FROM dim_organo")) == {1: "Local", 2: "Estatal"}


def test_calendario_del_anio_entero(con):
    assert filas(con, "SELECT count(*), min(fecha), max(fecha) FROM dim_fecha") == [
        (365, date(2026, 1, 1), date(2026, 12, 31))
    ]
    assert filas(con, "SELECT mes_anio, orden_mes_anio FROM dim_fecha WHERE fecha = DATE '2026-09-30'") == [
        ("sep 2026", 202609)
    ]


def test_una_clave_huerfana_para_la_exportacion(con, tmp_path):
    con.execute("DELETE FROM dim_organo WHERE id_organo = 1")
    errores = comprobar(con, PERIODO)
    assert any("id_organo" in e and "dim_organo" in e for e in errores)


def test_exportar_escribe_un_parquet_por_tabla_y_el_resumen(tmp_path):
    conexion = duckdb.connect()
    conexion.execute(ESQUEMA)
    datos = exportar(conexion, PERIODO, tmp_path)
    assert datos["filas"]["hechos_licitacion"] == 4
    assert datos["anuladas_excluidas"] == 1
    assert (tmp_path / "hechos_adjudicacion.parquet").exists()
    assert (tmp_path / "resumen.json").exists()
    leidas = duckdb.sql(f"SELECT count(*) FROM '{(tmp_path / 'hechos_licitacion.parquet').as_posix()}'").fetchone()
    assert leidas == (4,)


def test_exportar_no_escribe_nada_si_el_modelo_falla(tmp_path):
    conexion = duckdb.connect()
    conexion.execute(ESQUEMA)
    conexion.execute("INSERT INTO radar.public.lote VALUES (11, '1', -5)")
    conexion.execute("UPDATE radar.public.resultado SET importe_sin_iva = -1 WHERE id = 104")
    with pytest.raises(ModeloNoValido) as error:
        exportar(conexion, PERIODO, tmp_path)
    assert any("negativos" in e for e in error.value.errores)
    assert not list(tmp_path.glob("*.parquet"))


def test_un_periodo_de_dos_anios_no_vale():
    with pytest.raises(ValueError, match="mismo año"):
        Periodo(date(2025, 12, 1), date(2026, 1, 31))
