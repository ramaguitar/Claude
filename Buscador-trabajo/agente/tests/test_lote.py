import json

import pytest

from candidaturas.lote import cargar_lote, validar
from candidaturas.registro import Registro

FIRMA = "Ramiro Guitar\n+33 7 45 23 48 84\nramiroguitar28@gmail.com"


@pytest.fixture
def base(tmp_path):
    (tmp_path / "CVs").mkdir()
    (tmp_path / "CVs" / "cv.pdf").write_bytes(b"%PDF-1.4 prueba")
    return tmp_path


def mail(**cambios):
    m = {"zona": "Val d'Isère", "lugar": "Hôtel Le Blizzard", "tipo": "hotel",
         "web": "https://hotelblizzard.com", "email": "jobs@hotelblizzard.com", "idioma": "fr",
         "puesto": "Housekeeping", "cv": "CVs/cv.pdf", "vacante_url": None, "cv_nuevo": False,
         "asunto": "Candidature pour la saison d'hiver 2026/27",
         "cuerpo": "Madame, Monsieur,\n\nUn hôtel vit grâce à…\n\n" + FIRMA}
    m.update(cambios)
    return m


def test_mail_correcto_es_valido(base, tmp_path):
    validos, salteados = validar([mail(email=" Jobs@HotelBlizzard.com ")], Registro(tmp_path / "c.csv"), base)
    assert salteados == []
    assert validos[0]["email"] == "jobs@hotelblizzard.com"


@pytest.mark.parametrize("cambios, motivo", [
    ({"email": ""}, "faltan campos: email"),
    ({"email": "jobs@hotel"}, "email inválido"),
    ({"idioma": "pt"}, "idioma desconocido"),
    ({"cv": "CVs/no-existe.pdf"}, "CV inexistente"),
    ({"cuerpo": "Bonjour {LUGAR}\n" + FIRMA}, "marcador sin completar en cuerpo: {LUGAR}"),
    ({"asunto": "Candidature [PUESTO]"}, "marcador sin completar en asunto"),
    ({"cuerpo": "Bonjour, sans signature"}, "el cuerpo no tiene la firma"),
])
def test_mail_invalido_se_saltea_con_motivo(base, tmp_path, cambios, motivo):
    validos, salteados = validar([mail(**cambios)], Registro(tmp_path / "c.csv"), base)
    assert validos == []
    assert motivo in salteados[0]["motivo"]


def test_ya_contactado_se_saltea(base, tmp_path):
    reg = Registro(tmp_path / "c.csv")
    reg.agregar({"email": "info@hotelblizzard.com"})
    validos, salteados = validar([mail()], reg, base)
    assert validos == [] and "dominio ya contactado" in salteados[0]["motivo"]


def test_repetido_dentro_del_lote(base, tmp_path):
    lote = [mail(), mail(email="info@hotelblizzard.com"),
            mail(email="a@orange.fr"), mail(email="b@orange.fr")]
    validos, salteados = validar(lote, Registro(tmp_path / "c.csv"), base)
    assert [v["email"] for v in validos] == ["jobs@hotelblizzard.com", "a@orange.fr", "b@orange.fr"]
    assert "repetido dentro del lote" in salteados[0]["motivo"]


def test_un_mail_invalido_no_frena_al_resto(base, tmp_path):
    validos, salteados = validar([mail(email="mal"), mail()], Registro(tmp_path / "c.csv"), base)
    assert len(validos) == 1 and len(salteados) == 1


def test_cargar_lote_exige_lista(tmp_path):
    ruta = tmp_path / "2026-10-06.json"
    ruta.write_text(json.dumps({"no": "lista"}), encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_lote(ruta)
