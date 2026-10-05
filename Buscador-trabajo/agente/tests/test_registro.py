import csv
import json

import registrar_enviados
from candidaturas.registro import Registro, dominio, importar_enviados, normalizar_email


def leer_filas(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_normaliza_mayusculas_y_espacios():
    assert normalizar_email("  Info@Hotel-Alpin.CH ") == "info@hotel-alpin.ch"
    assert dominio("Jobs@Hotel-Alpin.ch") == "hotel-alpin.ch"


def test_registro_vacio_no_tiene_contactados(tmp_path):
    reg = Registro(tmp_path / "contactados.csv")
    assert reg.motivo_contactado("info@hotel.ch") is None


def test_agregar_crea_csv_con_encabezado_y_recuerda(tmp_path):
    ruta = tmp_path / "contactados.csv"
    reg = Registro(ruta)
    reg.agregar({"fecha": "2026-10-06", "lugar": "Hotel Alpin", "email": "Info@Hotel-Alpin.ch", "estado": "borrador"})
    assert "email ya contactado" in reg.motivo_contactado("info@hotel-alpin.ch")
    filas = leer_filas(ruta)
    assert filas[0]["email"] == "info@hotel-alpin.ch"
    assert filas[0]["dominio"] == "hotel-alpin.ch"
    # una instancia nueva lee lo persistido
    assert Registro(ruta).motivo_contactado("info@hotel-alpin.ch") is not None


def test_dominio_propio_bloquea_otras_direcciones(tmp_path):
    reg = Registro(tmp_path / "c.csv")
    reg.agregar({"email": "info@hotel-alpin.ch"})
    assert "dominio ya contactado" in reg.motivo_contactado("jobs@hotel-alpin.ch")


def test_dominio_generico_solo_bloquea_email_exacto(tmp_path):
    reg = Registro(tmp_path / "c.csv")
    reg.agregar({"email": "recrutement-lamontagne@orange.fr"})
    reg.agregar({"email": "hotel.soldeu@andorra.ad"})
    assert reg.motivo_contactado("otro-restaurant@orange.fr") is None
    assert reg.motivo_contactado("pensio@andorra.ad") is None
    assert reg.motivo_contactado("recrutement-lamontagne@orange.fr") is not None


def test_conserva_columnas_agregadas_por_el_usuario(tmp_path):
    ruta = tmp_path / "c.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "email", "estado", "respuesta"])
        w.writerow(["2026-09-24", "info@capra.ch", "enviado_manual", "rechazo"])
    reg = Registro(ruta)
    reg.agregar({"fecha": "2026-10-06", "email": "info@lagorge.ch", "estado": "borrador"})
    filas = leer_filas(ruta)
    assert list(filas[0].keys()) == ["fecha", "email", "estado", "respuesta"]
    assert filas[0]["respuesta"] == "rechazo"
    assert filas[1]["email"] == "info@lagorge.ch" and filas[1]["respuesta"] == ""


def test_importar_enviados_saltea_existentes_e_invalidos(tmp_path):
    reg = Registro(tmp_path / "c.csv")
    reg.agregar({"email": "info@capra.ch"})
    n = importar_enviados(reg, [
        {"email": "INFO@capra.ch", "fecha": "2026-09-24", "asunto": "x"},
        {"email": "jobs@hotel-mirabeau.ch", "fecha": "2026-10-01", "asunto": "Skifahren"},
        {"email": "sin-arroba", "fecha": "", "asunto": ""},
    ])
    assert n == 1
    assert "jobs@hotel-mirabeau.ch" in reg.emails


def test_cli_registrar_enviados(tmp_path, capsys):
    entrada = tmp_path / "enviados.json"
    entrada.write_text(json.dumps([{"email": "info@capra.ch", "fecha": "2026-09-24", "asunto": "Bewerbung"}]), encoding="utf-8")
    rc = registrar_enviados.main([str(entrada), "--registro", str(tmp_path / "c.csv")])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"importados": 1, "recibidos": 1}


def test_dominio_de_la_estacion_compartido_por_varios_negocios(tmp_path):
    reg = Registro(tmp_path / "c.csv")
    reg.agregar({"email": "mirabeau@verbier.ch"})
    assert reg.motivo_contactado("otrohotel@verbier.ch") is None
