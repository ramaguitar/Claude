import re
import unicodedata
from pathlib import Path

import pymupdf
import pytest

from candidaturas.cv_render import cargar_contenido

AGENTE = Path(__file__).resolve().parents[1]
CONTENIDOS = AGENTE / "cv" / "contenidos"
ORIGINALES = {
    "Barman": "CVs/Barman/CV-RamiroGuitar.pdf",
    "Plongeur": "CVs/Plongeur/Francés/CV-RamiroGuitar.pdf",
    "Tecnico": "CVs/Tecnico/CV-RamiroGuitar.pdf",
    "Vendedor-polivalente": "CVs/Vendedor-polivalente/Francés/CV-RamiroGuitar.pdf",
}


def palabras(texto: str) -> set[str]:
    t = unicodedata.normalize("NFKC", texto).replace("**", " ").replace("’", "'").lower()
    return set(re.findall(r"[\w']+", t))


def textos(c: dict) -> str:
    partes = [c["nombre"], c.get("titular", ""), c["contacto"]]
    for s in c["secciones"]:
        partes.append(s["titulo"])
        partes.append(s.get("texto", ""))
        for it in s.get("items", []):
            if isinstance(it, str):
                partes.append(it)
            else:
                partes += [it["puesto"], it["detalle"], *it.get("bullets", [])]
    return "\n".join(partes)


@pytest.mark.parametrize("puesto", sorted(ORIGINALES))
def test_contenido_fr_tiene_exactamente_las_palabras_del_pdf(puesto):
    c = cargar_contenido(CONTENIDOS / f"{puesto}.fr.json")
    with pymupdf.open(AGENTE.parent / ORIGINALES[puesto]) as d:
        del_pdf = palabras(d[0].get_text())
    del_json = palabras(textos(c))
    assert del_pdf - del_json == set(), f"faltan en el JSON: {sorted(del_pdf - del_json)}"
    assert del_json - del_pdf == set(), f"sobran en el JSON: {sorted(del_json - del_pdf)}"


def test_contenido_housekeeping_fr_es_valido():
    c = cargar_contenido(CONTENIDOS / "Housekeeping.fr.json")
    assert c["plantilla"] == "housekeeping" and c["idioma"] == "fr"
