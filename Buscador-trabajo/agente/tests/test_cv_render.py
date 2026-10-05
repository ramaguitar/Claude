import json

import pymupdf
import pytest

import cv
from candidaturas import cv_render

CONTENIDO = {
    "plantilla": "especifico", "puesto": "Barman", "idioma": "de", "nombre": "RAMIRO GUITAR",
    "titular": "Barkeeper | Cocktails",
    "contacto": "Telefon: +33 7 45 23 48 84 | E-Mail: ramiroguitar28@gmail.com",
    "secciones": [
        {"titulo": "BERUFSPROFIL", "tipo": "parrafo", "texto": "Grüsse & <Test> **fett**"},
        {"titulo": "ERFAHRUNG", "tipo": "experiencia",
         "items": [{"puesto": "Barkeeper", "detalle": "Hotel Abelux | Mallorca", "bullets": ["Cocktails"]}]},
        {"titulo": "SPRACHEN", "tipo": "lista", "vinetas": False, "items": ["**Sprachen:** Spanisch"]},
    ],
}


@pytest.fixture
def foto(tmp_path):
    ruta = tmp_path / "foto.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.clear_with(200)
    pix.save(ruta)
    return ruta


def test_inline_escapa_html_y_aplica_negrita():
    assert cv_render._inline("Grüsse & <Test> **fett**") == "Grüsse &amp; &lt;Test&gt; <b>fett</b>"


def test_a_html_incluye_todo_y_foto_embebida(foto):
    h = cv_render.a_html(CONTENIDO, foto, escala=0.94)
    assert "RAMIRO GUITAR" in h and "Barkeeper | Cocktails" in h
    assert "<b>Sprachen:</b> Spanisch" in h and 'class="sin-vinetas"' in h
    assert "data:image/png;base64," in h
    assert "--escala: 0.94" in h
    assert "{{" not in h


@pytest.mark.parametrize("roto", [
    {**CONTENIDO, "plantilla": "otra"},
    {**CONTENIDO, "secciones": [{"titulo": "X", "tipo": "tabla"}]},
    {k: v for k, v in CONTENIDO.items() if k != "nombre"},
])
def test_cargar_contenido_rechaza_contenido_invalido(tmp_path, roto):
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps(roto), encoding="utf-8")
    with pytest.raises(ValueError):
        cv_render.cargar_contenido(ruta)


def _simular(monkeypatch, secuencia_paginas):
    escalas = []
    monkeypatch.setattr(cv_render, "html_a_pdf", lambda html_txt, salida, navegador=None: escalas.append(html_txt))
    it = iter(secuencia_paginas)
    monkeypatch.setattr(cv_render, "paginas", lambda pdf: next(it))
    monkeypatch.setattr(cv_render, "previsualizar", lambda pdf, png, dpi=110: None)
    return escalas


def test_reduce_escala_hasta_que_entra_en_una_pagina(monkeypatch, foto, tmp_path):
    escalas = _simular(monkeypatch, [2, 2, 1])
    r = cv_render.renderizar(CONTENIDO, foto, tmp_path / "cv.pdf")
    assert r["ok"] is True and r["escala"] == 0.94 and len(escalas) == 3
    assert "--escala: 0.94" in escalas[-1]


def test_si_nunca_entra_reporta_ok_false(monkeypatch, foto, tmp_path):
    _simular(monkeypatch, [2] * len(cv_render.ESCALAS))
    r = cv_render.renderizar(CONTENIDO, foto, tmp_path / "cv.pdf")
    assert r["ok"] is False and r["escala"] == cv_render.ESCALAS[-1] and r["paginas"] == 2


def _hay_navegador():
    try:
        cv_render.buscar_navegador()
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _hay_navegador(), reason="sin Chrome/Edge")
def test_render_real_genera_pdf_de_una_pagina(foto, tmp_path):
    r = cv_render.renderizar(CONTENIDO, foto, tmp_path / "salida" / "CV.pdf")
    assert r["ok"] is True and r["paginas"] == 1
    with pymupdf.open(r["pdf"]) as d:
        assert "Grüsse" in d[0].get_text() and len(d[0].get_images()) == 1
    assert (tmp_path / "salida" / "CV.png").is_file()


def test_cli_registrar_actualiza_catalogo(tmp_path, capsys):
    base = tmp_path / "base"
    pdf = base / "CVs" / "Barman" / "Alemán" / "CV-RamiroGuitar.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    catalogo = tmp_path / "cvs.json"
    catalogo.write_text(json.dumps({"Barman": {"fr": "CVs/Barman/CV-RamiroGuitar.pdf"}}), encoding="utf-8")
    rc = cv.main(["--catalogo", str(catalogo), "--base", str(base), "registrar", "Barman", "de", str(pdf)])
    assert rc == 0
    assert json.loads(catalogo.read_text(encoding="utf-8"))["Barman"] == {
        "fr": "CVs/Barman/CV-RamiroGuitar.pdf", "de": "CVs/Barman/Alemán/CV-RamiroGuitar.pdf"}
