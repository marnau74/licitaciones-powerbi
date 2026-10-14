"""Las cifras de control sobre la base en miniatura, comprobadas a mano."""

import duckdb
import pytest

from preparar.cifras import calcular, markdown
from preparar.exportar import exportar
from tests.test_exportar import ESQUEMA, PERIODO


@pytest.fixture
def cifras(tmp_path):
    con = duckdb.connect()
    con.execute(ESQUEMA)
    resumen = exportar(con, PERIODO, tmp_path)
    return calcular(tmp_path), resumen


def test_medidas(cifras):
    medidas = cifras[0]["medidas"]
    assert medidas["Licitaciones"] == 4
    assert medidas["Importe licitado"] == 250000
    # Baja: solo los tres resultados comparables. 1 - (96.000 + 80.000 + 40.000) / (120.000 + 80.000 + 50.000).
    assert medidas["% de baja"] == pytest.approx(1 - 216000 / 250000)
    # Ofertas de los cuatro adjudicados: 4, 1, 2 y 3.
    assert medidas["Ofertas por adjudicación"] == pytest.approx(2.5)
    assert medidas["% con una sola oferta"] == pytest.approx(0.25)
    assert medidas["% desiertos"] == pytest.approx(1 / 5)
    assert medidas["Adjudicatarios distintos"] == 2
    assert medidas["% del importe a pymes"] == pytest.approx(540000 / 716000)
    assert medidas["Cuota de los 10 primeros adjudicatarios"] == pytest.approx(1)


def test_desglose_por_mes(cifras):
    por_mes = cifras[0]["desgloses"][0]["filas"]
    assert por_mes == [["enero", 1], ["marzo", 1], ["mayo", 1], ["septiembre", 1]]


def test_documento(cifras):
    texto = markdown(*cifras)
    assert "| % de baja | 13,6 % |" in texto
    assert "| Importe licitado | 250.000 € |" in texto
