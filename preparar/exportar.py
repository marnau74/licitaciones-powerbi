"""Exporta el modelo en estrella del informe a Parquet, leyendo la base PostgreSQL del radar de licitaciones.

    uv run python -m preparar.exportar --postgres "host=localhost port=5434 dbname=radar user=radar password=radar"

Escribe en `datos/` una tabla por fichero y `datos/resumen.json` con los recuentos. Antes de escribir comprueba el
modelo (claves únicas, ninguna clave huérfana, importes no negativos, ninguna licitación perdida) y se para si algo
falla: un Parquet con errores no llega a Power BI.
"""

from __future__ import annotations

import argparse
import json
import secrets
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

SQL = Path(__file__).with_name("modelo.sql")

# NIF de persona física: DNI (8 cifras y letra) o NIE y similares (K, L, M, X, Y, Z, 7 cifras y letra), con o sin «ES».
NIF_DE_PERSONA = r"^(ES)?([0-9]{8}|[KLMXYZ][0-9]{7})[A-Z]$"

# NIF de una entidad española: letra de la forma jurídica, 7 cifras y el carácter de control.
NIF_DE_ENTIDAD = r"^(ES)?[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$"

# Palabras que delatan que el adjudicatario es una organización (forma jurídica, tipo de entidad o actividad). Hacen
# falta porque muchos NIF llegan mal: recortados («0002»), sin letra, con una cifra de más o extranjeros.
ORGANIZACION = (
    r"(?i)\b(S\.?\s?L\.?(\s?U\.?)?|S\.?\s?A\.?(\s?U\.?)?|S\.?\s?COOP\.?|SOCIEDAD|COOPERATIVA|U\.?\s?T\.?\s?E\.?|"
    r"LTDA?\.?|LIMITED|GMBH|INC\.?|LLC|LLP|PLC|B\.?\s?V\.?|N\.?\s?V\.?|S\.?R\.?L\.?|SARL|SAS|S\.?P\.?A\.?|AG|AB|OY|"
    r"A/S|APS|LDA|CORP\.?|CORPORATION|COMPANY|CO\.|GROUP|GRUPO|FUNDACI[OÓ]N|FOUNDATION|FONDATION|STIFTUNG|"
    r"ASOCIACI[OÓ]N|ASSOCIATION|ASSOCIATES|INSTITUT\w*|UNIVERSI\w*|AYUNTAMIENTO|CONSORCIO|COLEGIO|CLUB|FEDERACI\w*|"
    r"FEDERATION|CENT(RO|ER|RE)|THEAT(RE|ER)|TEATRO|D\.?O\.?O\.?|PTY|O[UÜ]|KFT|LIMITADA|C\.?\s?B\.?|S\.?C\.?P\.?|"
    r"SOCI[EÉ]T[EÉ]|GESELLSCHAFT|E\.?\s?V\.?|ORGANI[SZ]ATION|COUNCIL|NETWORK|SERVICES|SERVICIOS|SOLUTIONS|SOLUCIONES|"
    r"SYSTEMS|SISTEMAS|TECHNOLOG\w*|TECNOLOG\w*|LABORATOR\w*|CONSULTING|CONSULTOR\w*|ACADEM\w*|MUSE(UM|O)|ORCHEST\w*|"
    r"ORQUESTA|BANK|BANCO|INSURANCE|SEGUROS|INTERNATIONAL|GLOBAL|MINISTER\w*|GOVERNMENT|GOBIERNO|EMBAJADA|EMBASSY|"
    r"EDITORIAL|PUBLISHING|PRESS|HOTEL|AIRLINES|PRODUCTIONS?|PRODUCCIONES|STUDIOS?|ESTUDIO|AGENC\w*|EXPERTOS|"
    r"ARQUITECTOS|ABOGADOS|ASESORES|INGENIER\w*|ENGINEERING|COMMUNICATIONS|COMUNICACI\w*|MEDIA|EXPORTS?|TRADING|"
    r"GALLERY|GALER[IÍ]A|DIGITAL|ANALYTICS|ENGINES|EQUIPMENT|MANAGEMENT|EXHIBITION|PROPERTY|CONFIDENCIAL|LICITADORES|"
    r"VARIOS)\b"
)

# Tabla -> clave primaria.
CLAVES = {
    "hechos_licitacion": "id_licitacion",
    "hechos_adjudicacion": "id_resultado",
    "dim_fecha": "fecha",
    "dim_organo": "id_organo",
    "dim_territorio": "cod_territorio",
    "dim_tipo_contrato": "cod_tipo_contrato",
    "dim_procedimiento": "cod_procedimiento",
    "dim_estado": "cod_estado",
    "dim_resultado": "cod_resultado",
    "dim_cpv": "cod_cpv_division",
    "dim_adjudicatario": "nif_adjudicatario",
}

# (tabla de hechos, columna) -> dimensión. Son las relaciones del modelo de Power BI.
RELACIONES = {
    ("hechos_licitacion", "fecha_publicacion"): "dim_fecha",
    ("hechos_licitacion", "id_organo"): "dim_organo",
    ("hechos_licitacion", "cod_territorio"): "dim_territorio",
    ("hechos_licitacion", "cod_tipo_contrato"): "dim_tipo_contrato",
    ("hechos_licitacion", "cod_procedimiento"): "dim_procedimiento",
    ("hechos_licitacion", "cod_estado"): "dim_estado",
    ("hechos_licitacion", "cod_cpv_division"): "dim_cpv",
    ("hechos_adjudicacion", "fecha_publicacion"): "dim_fecha",
    ("hechos_adjudicacion", "id_organo"): "dim_organo",
    ("hechos_adjudicacion", "cod_territorio"): "dim_territorio",
    ("hechos_adjudicacion", "cod_tipo_contrato"): "dim_tipo_contrato",
    ("hechos_adjudicacion", "cod_procedimiento"): "dim_procedimiento",
    ("hechos_adjudicacion", "cod_cpv_division"): "dim_cpv",
    ("hechos_adjudicacion", "cod_resultado"): "dim_resultado",
    ("hechos_adjudicacion", "nif_adjudicatario"): "dim_adjudicatario",
}


class ModeloNoValido(Exception):
    def __init__(self, errores: list[str]) -> None:
        super().__init__("El modelo no supera las comprobaciones:\n- " + "\n- ".join(errores))
        self.errores = errores


@dataclass(frozen=True)
class Periodo:
    desde: date
    hasta: date

    def __post_init__(self) -> None:
        if self.desde > self.hasta or self.desde.year != self.hasta.year:
            raise ValueError("El periodo tiene que estar dentro de un mismo año")


def construir(con: duckdb.DuckDBPyConnection, periodo: Periodo) -> None:
    """Crea las tablas del modelo en `con`, que tiene que tener la base del radar enganchada como `radar`."""
    sql = SQL.read_text(encoding="utf-8").format(desde=periodo.desde, hasta=periodo.hasta, anio=periodo.desde.year)
    con.execute(sql)
    seudonimizar(con)


def seudonimizar(con: duckdb.DuckDBPyConnection) -> None:
    """Quita los datos personales de los adjudicatarios que son personas físicas (autónomos).

    La Plataforma de Contratación publica su nombre y su DNI, pero eso no justifica redistribuirlos en bloque. Su NIF se
    cambia por un código que sale de un resumen con una sal aleatoria que no se guarda: es el mismo en las dos tablas
    (la relación del modelo sigue funcionando y se pueden contar) pero no se puede volver al DNI.

    Con un NIF de persona, el nombre pasa a ser «Persona física». Muchos NIF llegan mal escritos o recortados; si el NIF
    no es el de una entidad española y el nombre no tiene nada de organización, se trata igual y el nombre pasa a ser
    «Posible persona física»: ante la duda, se protege. Las empresas y las administraciones no cambian.
    """
    sal = secrets.token_hex(16)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE seudonimos AS
        SELECT
            nif_adjudicatario AS nif,
            'PF-' || upper(substr(sha256(nif_adjudicatario || ?), 1, 12)) AS codigo,
            CASE WHEN regexp_matches(nif_adjudicatario, '{NIF_DE_PERSONA}') THEN 'Persona física'
                 ELSE 'Posible persona física' END AS nombre
        FROM dim_adjudicatario
        WHERE regexp_matches(nif_adjudicatario, '{NIF_DE_PERSONA}')
           OR (nif_adjudicatario <> 'SIN-NIF'
               AND NOT regexp_matches(nif_adjudicatario, '{NIF_DE_ENTIDAD}')
               AND NOT regexp_matches(coalesce(adjudicatario, ''), '{ORGANIZACION}'))
        """,
        [sal],
    )
    con.execute(
        "UPDATE hechos_adjudicacion AS h SET nif_adjudicatario = s.codigo FROM seudonimos AS s "
        "WHERE h.nif_adjudicatario = s.nif"
    )
    con.execute(
        "UPDATE dim_adjudicatario AS d SET nif_adjudicatario = s.codigo, adjudicatario = s.nombre "
        "FROM seudonimos AS s WHERE d.nif_adjudicatario = s.nif"
    )
    con.execute("DROP TABLE seudonimos")


def comprobar(con: duckdb.DuckDBPyConnection, periodo: Periodo) -> list[str]:
    """Las comprobaciones del modelo. Devuelve los errores encontrados (vacío si todo está bien)."""
    errores: list[str] = []

    def uno(sql: str) -> int:
        return con.execute(sql).fetchone()[0]

    for tabla, clave in CLAVES.items():
        repetidas = uno(f"SELECT count(*) - count(DISTINCT {clave}) FROM {tabla}")
        nulas = uno(f"SELECT count(*) FROM {tabla} WHERE {clave} IS NULL")
        if repetidas or nulas:
            errores.append(f"{tabla}.{clave}: {repetidas} repetidas y {nulas} nulas")

    for (hechos, columna), dimension in RELACIONES.items():
        clave = CLAVES[dimension]
        huerfanas = uno(
            f"SELECT count(*) FROM {hechos} h WHERE NOT EXISTS "
            f"(SELECT 1 FROM {dimension} d WHERE d.{clave} = h.{columna})"
        )
        if huerfanas:
            errores.append(f"{hechos}.{columna}: {huerfanas} filas sin su fila en {dimension}")

    for tabla, columna in [
        ("hechos_licitacion", "importe_sin_iva"),
        ("hechos_licitacion", "valor_estimado"),
        ("hechos_adjudicacion", "importe_adjudicado"),
        ("hechos_adjudicacion", "importe_licitado"),
        ("hechos_adjudicacion", "ofertas_recibidas"),
    ]:
        negativos = uno(f"SELECT count(*) FROM {tabla} WHERE {columna} < 0")
        if negativos:
            errores.append(f"{tabla}.{columna}: {negativos} valores negativos")

    # Ninguna licitación del periodo se pierde por el camino (se compara mes a mes con la base).
    diferencias = con.execute(f"""
        SELECT mes, en_base, en_modelo FROM (
            SELECT month(fecha_publicacion) AS mes, count(*) AS en_base
            FROM radar.public.licitacion
            WHERE fecha_publicacion BETWEEN DATE '{periodo.desde}' AND DATE '{periodo.hasta}' AND NOT anulada
            GROUP BY ALL
        ) b FULL JOIN (
            SELECT month(fecha_publicacion) AS mes, count(*) AS en_modelo FROM hechos_licitacion GROUP BY ALL
        ) m USING (mes)
        WHERE en_base IS DISTINCT FROM en_modelo
    """).fetchall()
    errores.extend(
        f"Mes {mes}: {base} licitaciones en la base y {modelo} en el modelo" for mes, base, modelo in diferencias
    )
    return errores


def resumen(con: duckdb.DuckDBPyConnection, periodo: Periodo) -> dict:
    filas = {tabla: con.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0] for tabla in CLAVES}
    anuladas = con.execute(
        f"SELECT count(*) FROM radar.public.licitacion WHERE anulada "
        f"AND fecha_publicacion BETWEEN DATE '{periodo.desde}' AND DATE '{periodo.hasta}'"
    ).fetchone()[0]
    return {"desde": str(periodo.desde), "hasta": str(periodo.hasta), "filas": filas, "anuladas_excluidas": anuladas}


def exportar(con: duckdb.DuckDBPyConnection, periodo: Periodo, salida: Path) -> dict:
    construir(con, periodo)
    errores = comprobar(con, periodo)
    if errores:
        raise ModeloNoValido(errores)
    salida.mkdir(parents=True, exist_ok=True)
    for tabla in CLAVES:
        destino = (salida / f"{tabla}.parquet").as_posix()
        con.execute(f"COPY (SELECT * FROM {tabla} ORDER BY {CLAVES[tabla]}) TO '{destino}' (FORMAT parquet)")
    datos = resumen(con, periodo)
    (salida / "resumen.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datos


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--postgres", required=True, help="Cadena de conexión libpq de la base del radar")
    argumentos.add_argument("--desde", type=date.fromisoformat, default=date(2026, 1, 1))
    argumentos.add_argument("--hasta", type=date.fromisoformat, default=date(2026, 9, 30))
    argumentos.add_argument("--salida", type=Path, default=Path("datos"))
    a = argumentos.parse_args()

    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres;")
    conexion = a.postgres.replace("'", "''")
    con.execute(f"ATTACH '{conexion}' AS radar (TYPE postgres, READ_ONLY)")
    datos = exportar(con, Periodo(a.desde, a.hasta), a.salida)
    print(json.dumps(datos, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
