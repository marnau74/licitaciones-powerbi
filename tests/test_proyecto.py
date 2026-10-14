"""La estructura del proyecto de Power BI (PBIP): que cada fichero apunte a algo que existe."""

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INFORME = RAIZ / "Contratacion.Report"
MODELO = RAIZ / "Contratacion.SemanticModel" / "definition"


def leer(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_el_pbip_apunta_al_informe_y_el_informe_al_modelo():
    pbip = leer(RAIZ / "Contratacion.pbip")
    assert (RAIZ / pbip["artifacts"][0]["report"]["path"]).is_dir()
    pbir = leer(INFORME / "definition.pbir")
    assert (INFORME / pbir["datasetReference"]["byPath"]["path"] / "definition.pbism").is_file()


def test_las_paginas_del_indice_existen_y_tienen_su_nombre():
    indice = leer(INFORME / "definition" / "pages" / "pages.json")
    carpetas = {p.name for p in (INFORME / "definition" / "pages").iterdir() if p.is_dir()}
    assert set(indice["pageOrder"]) == carpetas
    assert indice["activePageName"] in carpetas
    for nombre in indice["pageOrder"]:
        assert leer(INFORME / "definition" / "pages" / nombre / "page.json")["name"] == nombre


def test_el_tema_registrado_existe_y_usa_la_paleta_del_radar():
    informe = leer(INFORME / "definition" / "report.json")
    tema = informe["themeCollection"]["customTheme"]["name"]
    assert (INFORME / "StaticResources" / "RegisteredResources" / tema).is_file()
    colores = leer(INFORME / "StaticResources" / "RegisteredResources" / tema)["dataColors"]
    assert colores[0] == "#1D4ED8"


def test_cada_tabla_del_modelo_esta_declarada_y_tiene_su_fichero():
    declaradas = {
        m.group(1).strip("'")
        for m in re.finditer(r"^ref table (.+)$", (MODELO / "model.tmdl").read_text(encoding="utf-8"), re.M)
    }
    ficheros = {f.stem for f in (MODELO / "tables").glob("*.tmdl")}
    assert declaradas == ficheros


def test_cada_parquet_que_lee_el_modelo_lo_escribe_la_exportacion():
    from preparar.exportar import CLAVES

    leidos = set()
    for fichero in (MODELO / "tables").glob("*.tmdl"):
        leidos |= set(re.findall(r'CarpetaDeDatos & "(\w+)\.parquet"', fichero.read_text(encoding="utf-8")))
    assert leidos == set(CLAVES)
