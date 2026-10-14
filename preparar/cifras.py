"""Cifras de control: lo que tienen que dar las medidas principales del modelo, calculado con DuckDB sobre los mismos
Parquet y con las mismas definiciones. Sirven para comprobar el DAX en Power BI.

    uv run python -m preparar.cifras            # escribe docs/cifras-de-control.md y datos/cifras.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

# Nombre de la medida en el modelo -> SQL que la calcula sobre las vistas de los Parquet.
ADJUDICADO = "adjudicado"
MEDIDAS = {
    "Licitaciones": "SELECT count(*) FROM hechos_licitacion",
    "Importe licitado": "SELECT sum(importe_sin_iva) FROM hechos_licitacion",
    "Importe medio": "SELECT avg(importe_sin_iva) FROM hechos_licitacion",
    "Importe mediano": "SELECT median(importe_sin_iva) FROM hechos_licitacion",
    "% con fondos UE": "SELECT avg(CASE WHEN financiacion_ue THEN 1 ELSE 0 END) FROM hechos_licitacion",
    "Días de plazo (mediana)": "SELECT median(dias_de_plazo) FROM hechos_licitacion",
    "Adjudicaciones": f"SELECT count(*) FROM hechos_adjudicacion WHERE {ADJUDICADO}",
    "Importe adjudicado": f"SELECT sum(importe_adjudicado) FROM hechos_adjudicacion WHERE {ADJUDICADO}",
    "% de baja": f"""
        SELECT 1 - sum(importe_adjudicado) / sum(importe_licitado)
        FROM hechos_adjudicacion WHERE {ADJUDICADO} AND importe_comparable""",
    "Ofertas por adjudicación": f"""
        SELECT avg(ofertas_recibidas) FROM hechos_adjudicacion WHERE {ADJUDICADO} AND ofertas_recibidas >= 1""",
    "% con una sola oferta": f"""
        SELECT avg(CASE WHEN ofertas_recibidas = 1 THEN 1 ELSE 0 END)
        FROM hechos_adjudicacion WHERE {ADJUDICADO} AND ofertas_recibidas >= 1""",
    "% del importe a pymes": f"""
        SELECT sum(CASE WHEN pyme THEN importe_adjudicado END) / sum(importe_adjudicado)
        FROM hechos_adjudicacion WHERE {ADJUDICADO}""",
    "% desiertos": "SELECT avg(CASE WHEN desierto THEN 1 ELSE 0 END) FROM hechos_adjudicacion",
    "Adjudicatarios distintos": f"""
        SELECT count(DISTINCT nif_adjudicatario) FROM hechos_adjudicacion
        WHERE {ADJUDICADO} AND nif_adjudicatario <> 'SIN-NIF'""",
    "Cuota de los 10 primeros adjudicatarios": f"""
        WITH por_empresa AS (
            SELECT nif_adjudicatario, sum(importe_adjudicado) AS importe
            FROM hechos_adjudicacion WHERE {ADJUDICADO} GROUP BY ALL
        )
        SELECT (SELECT sum(importe) FROM (SELECT importe FROM por_empresa WHERE nif_adjudicatario <> 'SIN-NIF'
                                          ORDER BY importe DESC LIMIT 10))
               / (SELECT sum(importe) FROM por_empresa)""",
}

# Desgloses: (título, columna de la dimensión en el modelo, SQL que devuelve (valor, licitaciones)).
DESGLOSES = [
    (
        "Licitaciones por mes de publicación",
        "Fecha[Mes]",
        """SELECT f.nombre_mes, count(*) FROM hechos_licitacion h JOIN dim_fecha f ON f.fecha = h.fecha_publicacion
           GROUP BY f.nombre_mes, f.mes ORDER BY f.mes""",
    ),
    (
        "Licitaciones por tipo de contrato",
        "'Tipo de contrato'[Tipo de contrato]",
        """SELECT t.tipo_contrato, count(*) FROM hechos_licitacion h
           JOIN dim_tipo_contrato t USING (cod_tipo_contrato) GROUP BY ALL ORDER BY 2 DESC""",
    ),
    (
        "Licitaciones por comunidad (las cinco con más)",
        "Territorio[Comunidad]",
        """SELECT t.comunidad, count(*) FROM hechos_licitacion h
           JOIN dim_territorio t USING (cod_territorio) GROUP BY ALL ORDER BY 2 DESC LIMIT 5""",
    ),
]


def calcular(carpeta: Path) -> dict:
    con = duckdb.connect()
    for fichero in sorted(carpeta.glob("*.parquet")):
        con.execute(f"CREATE VIEW {fichero.stem} AS SELECT * FROM '{fichero.as_posix()}'")
    medidas = {nombre: _numero(con.execute(sql).fetchone()[0]) for nombre, sql in MEDIDAS.items()}
    desgloses = [
        {"titulo": titulo, "columna": columna, "filas": [[v, n] for v, n in con.execute(sql).fetchall()]}
        for titulo, columna, sql in DESGLOSES
    ]
    return {"medidas": medidas, "desgloses": desgloses}


def _numero(valor) -> float | int | None:
    if valor is None:
        return None
    return int(valor) if float(valor).is_integer() else float(valor)


def _formato(nombre: str, valor) -> str:
    if valor is None:
        return "(en blanco)"
    if nombre.startswith("%") or nombre.startswith("Cuota"):
        return f"{valor * 100:.1f} %".replace(".", ",")
    if "Importe" in nombre:
        return f"{valor:,.0f} €".replace(",", ".")
    if isinstance(valor, float):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{valor:,}".replace(",", ".")


def markdown(cifras: dict, resumen: dict) -> str:
    lineas = [
        "# Cifras de control",
        "",
        "Lo que tienen que dar las medidas del modelo sin ningún filtro, calculado con DuckDB sobre los mismos Parquet",
        "(`preparar/cifras.py`). Si una medida de Power BI no coincide, el error está en el DAX o en el modelo.",
        "",
        f"Periodo: del {resumen['desde']} al {resumen['hasta']} (fecha de publicación). "
        f"Licitaciones anuladas excluidas: {resumen['anuladas_excluidas']:,}.".replace(",", "."),
        "",
        "| Medida | Valor esperado |",
        "|---|---:|",
    ]
    lineas += [f"| {n} | {_formato(n, v)} |" for n, v in cifras["medidas"].items()]
    for d in cifras["desgloses"]:
        lineas += ["", f"## {d['titulo']}", "", f"`{d['columna']}` con la medida `[Licitaciones]`.", ""]
        lineas += ["| | Licitaciones |", "|---|---:|"]
        lineas += [f"| {v} | {_formato('n', n)} |" for v, n in d["filas"]]
    return "\n".join(lineas) + "\n"


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--datos", type=Path, default=Path("datos"))
    argumentos.add_argument("--documento", type=Path, default=Path("docs/cifras-de-control.md"))
    a = argumentos.parse_args()
    cifras = calcular(a.datos)
    resumen = json.loads((a.datos / "resumen.json").read_text(encoding="utf-8"))
    (a.datos / "cifras.json").write_text(json.dumps(cifras, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    a.documento.write_text(markdown(cifras, resumen), encoding="utf-8")
    print(a.documento.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
