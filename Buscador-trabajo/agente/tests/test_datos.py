import json
from pathlib import Path

AGENTE = Path(__file__).resolve().parents[1]
BASE = AGENTE.parent


def test_cvs_json_apunta_a_pdfs_existentes():
    catalogo = json.loads((AGENTE / "cvs.json").read_text(encoding="utf-8"))
    assert set(catalogo) == {"Housekeeping", "Barman", "Plongeur", "Tecnico", "Vendedor-polivalente"}
    for puesto, por_idioma in catalogo.items():
        for idioma, ruta in por_idioma.items():
            assert (BASE / ruta).is_file(), f"{puesto}/{idioma}: no existe {ruta}"


def test_zonas_json_bien_formado():
    zonas = json.loads((AGENTE / "zonas.json").read_text(encoding="utf-8"))
    assert len(zonas) >= 50
    nombres = [z["nombre"] for z in zonas]
    assert len(nombres) == len(set(nombres))
    for z in zonas:
        assert z["idioma"] in {"fr", "de", "it", "ca"}
        assert z["estado"] in {"pendiente", "en_curso", "cubierta"}
        assert z["pais"] in {"Francia", "Suiza", "Italia", "Andorra"}


def test_plantillas_de_mail_tienen_firma_y_marcadores():
    for idioma in ("fr", "de", "en", "it", "ca"):
        texto = (AGENTE / "plantillas" / f"{idioma}.md").read_text(encoding="utf-8")
        assert "ramiroguitar28@gmail.com" in texto and "+33 7 45 23 48 84" in texto
        assert "{LUGAR}" in texto and "{ZONA}" in texto and "{GANCHO}" in texto
        assert ("{PERMISO}" in texto) == (idioma != "ca")
