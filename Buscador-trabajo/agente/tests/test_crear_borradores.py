import json
from pathlib import Path

import pytest

import crear_borradores
from candidaturas.registro import Registro

FIRMA = "Ramiro Guitar\n+33 7 45 23 48 84\nramiroguitar28@gmail.com"
AGENTE = Path(__file__).resolve().parents[1]


class FakeIMAP:
    def __init__(self, fallar_en=None):
        self.appends = []
        self.fallar_en = fallar_en
        self.cerrado = False

    def list(self):
        return "OK", [rb'(\HasNoChildren) "/" "INBOX"', rb'(\Drafts \HasNoChildren) "/" "[Gmail]/Borradores"']

    def append(self, carpeta, flags, fecha, datos):
        if self.fallar_en is not None and len(self.appends) == self.fallar_en:
            raise OSError("conexión perdida")
        self.appends.append((carpeta, flags, datos))
        return "OK", [b"APPEND completed"]

    def logout(self):
        self.cerrado = True


@pytest.fixture(autouse=True)
def sin_credenciales_del_sistema(monkeypatch):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)


@pytest.fixture
def entorno(tmp_path, hacer_pdf):
    base = tmp_path / "base"
    hacer_pdf(base / "CVs" / "cv.pdf")
    catalogo = tmp_path / "cvs.json"
    catalogo.write_text(json.dumps({"Housekeeping": {"de": "CVs/cv.pdf"}}), encoding="utf-8")
    mails = [{"zona": "Zermatt", "lugar": f"Hotel {i}", "tipo": "hotel", "web": f"https://hotel{i}.ch",
              "email": f"info@hotel{i}.ch", "idioma": "de", "puesto": "Housekeeping", "cv": "CVs/cv.pdf",
              "vacante_url": None, "cv_nuevo": False, "asunto": "Bewerbung für die Wintersaison 2026/27",
              "cuerpo": "Sehr geehrte Damen und Herren\n\n" + FIRMA} for i in range(2)]
    lote = tmp_path / "2026-10-06.json"
    lote.write_text(json.dumps(mails, ensure_ascii=False), encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("GMAIL_USER=ramiroguitar28@gmail.com\nGMAIL_APP_PASSWORD=clave-de-prueba\n", encoding="utf-8")
    registro = tmp_path / "contactados.csv"
    args = [str(lote), "--base", str(base), "--registro", str(registro), "--env", str(env),
            "--catalogo", str(catalogo)]
    return args, registro, env


def correr(args, capsys, conectar):
    rc = crear_borradores.main(args, conectar=conectar)
    return rc, json.loads(capsys.readouterr().out)


def test_crea_borradores_y_registra(entorno, capsys):
    args, registro, _ = entorno
    fake = FakeIMAP()
    rc, salida = correr(args, capsys, lambda u, p: fake)
    assert rc == 0 and len(salida["creados"]) == 2 and salida["errores"] == []
    assert [a[0] for a in fake.appends] == ['"[Gmail]/Borradores"'] * 2
    assert fake.cerrado
    assert Registro(registro).emails == {"info@hotel0.ch", "info@hotel1.ch"}


def test_reejecutar_el_mismo_lote_no_duplica(entorno, capsys):
    args, _, _ = entorno
    correr(args, capsys, lambda u, p: FakeIMAP())
    fake = FakeIMAP()
    rc, salida = correr(args, capsys, lambda u, p: fake)
    assert rc == 0 and fake.appends == [] and len(salida["salteados"]) == 2


def test_corte_a_mitad_registra_solo_lo_creado_y_se_completa_al_reintentar(entorno, capsys):
    args, registro, _ = entorno
    rc, salida = correr(args, capsys, lambda u, p: FakeIMAP(fallar_en=1))
    assert rc == 1 and "Re-ejecutá" in salida["errores"][0]
    assert Registro(registro).emails == {"info@hotel0.ch"}
    fake = FakeIMAP()
    rc, salida = correr(args, capsys, lambda u, p: fake)
    assert rc == 0 and len(fake.appends) == 1
    assert [c["email"] for c in salida["creados"]] == ["info@hotel1.ch"]


def test_dry_run_no_conecta_ni_registra(entorno, capsys):
    args, registro, _ = entorno

    def no_conectar(u, p):
        raise AssertionError("dry-run no debe conectar")

    rc, salida = correr(args + ["--dry-run"], capsys, no_conectar)
    assert rc == 0 and len(salida["creados"]) == 2 and salida["dry_run"] is True
    assert not registro.exists()


def test_sin_credenciales_falla_claro(entorno, capsys):
    args, _, env = entorno
    env.write_text("", encoding="utf-8")
    rc, salida = correr(args, capsys, lambda u, p: FakeIMAP())
    assert rc == 2 and "GMAIL_APP_PASSWORD" in salida["errores"][0]


def test_solo_gmail_smtp_puede_enviar():
    # el envío está confinado a un único módulo, que solo usa crear_borradores.py --enviar
    for py in list(AGENTE.glob("*.py")) + list((AGENTE / "candidaturas").glob("*.py")):
        if py.name == "gmail_smtp.py":
            continue
        texto = py.read_text(encoding="utf-8")
        for prohibido in ("smtplib", "send_message", "sendmail"):
            assert prohibido not in texto, f"{py.name} contiene {prohibido}"


def test_registro_bloqueado_aborta_antes_de_tocar_gmail(entorno, capsys):
    args, registro, _ = entorno
    registro.mkdir()  # como si estuviera abierto en Excel: no se puede escribir

    def no_conectar(u, p):
        raise AssertionError("no debe conectar si no puede registrar")

    rc, salida = correr(args, capsys, no_conectar)
    assert rc == 2 and "contactados.csv" in salida["errores"][0]


def test_fallo_al_registrar_tras_crear_borrador_pide_no_reintentar(entorno, capsys, monkeypatch):
    args, _, _ = entorno

    def agregar_roto(self, fila):
        raise PermissionError("archivo bloqueado")

    monkeypatch.setattr(crear_borradores.Registro, "agregar", agregar_roto)
    fake = FakeIMAP()
    rc, salida = correr(args, capsys, lambda u, p: fake)
    assert rc == 3 and len(fake.appends) == 1
    assert "NO re-ejecutes" in salida["errores"][0] and "info@hotel0.ch" in salida["errores"][0]


# ---------- modo --enviar ----------

class FakeSMTP:
    def __init__(self, fallar_en=None):
        self.enviados = []
        self.fallar_en = fallar_en
        self.cerrado = False

    def send_message(self, msg, from_addr=None, to_addrs=None):
        if self.fallar_en is not None and len(self.enviados) == self.fallar_en:
            raise OSError("smtp cortado")
        self.enviados.append((to_addrs, msg))
        return {}

    def quit(self):
        self.cerrado = True


def prohibido(u, p):
    raise AssertionError("no debe conectar")


def correr_envio(args, capsys, imap=prohibido, smtp=prohibido, pausas=None):
    pausas = [] if pausas is None else pausas
    rc = crear_borradores.main(args + ["--enviar"], conectar=imap, conectar_smtp=smtp, dormir=pausas.append)
    return rc, json.loads(capsys.readouterr().out)


def leer_estados(registro):
    import csv
    with registro.open(encoding="utf-8-sig", newline="") as f:
        return {r["email"]: r["estado"] for r in csv.DictReader(f)}


def test_enviar_envia_cada_mail_y_lo_registra_como_enviado(entorno, capsys):
    args, registro, _ = entorno
    smtp, pausas = FakeSMTP(), []
    rc, salida = correr_envio(args, capsys, smtp=lambda u, p: smtp, pausas=pausas)
    assert rc == 0 and salida["errores"] == []
    assert [e["email"] for e in salida["enviados"]] == ["info@hotel0.ch", "info@hotel1.ch"]
    assert salida["creados"] == []
    assert [to for to, _ in smtp.enviados] == [["info@hotel0.ch"], ["info@hotel1.ch"]]
    assert smtp.cerrado
    assert len(pausas) == 1 and 45 <= pausas[0] <= 90  # espaciado aleatorio entre envíos
    assert leer_estados(registro) == {"info@hotel0.ch": "enviado", "info@hotel1.ch": "enviado"}


def test_cv_traducido_pendiente_de_aprobacion_queda_en_borrador(entorno, capsys, tmp_path):
    args, registro, _ = entorno
    pendientes = tmp_path / "cvs_pendientes.json"
    pendientes.write_text(json.dumps(["CVs/cv.pdf"]), encoding="utf-8")
    imap = FakeIMAP()
    rc, salida = correr_envio(args + ["--pendientes", str(pendientes)], capsys, imap=lambda u, p: imap)
    assert rc == 0 and salida["enviados"] == [] and len(imap.appends) == 2
    assert all("pendiente de aprobación" in c["motivo_borrador"] for c in salida["creados"])
    assert set(leer_estados(registro).values()) == {"borrador"}


def test_tope_diario_deja_el_excedente_en_borrador(entorno, capsys):
    args, registro, _ = entorno
    from datetime import date
    reg = Registro(registro)
    for i in range(39):
        reg.agregar({"fecha": date.today().isoformat(), "email": f"x{i}@otro{i}.ch", "estado": "enviado"})
    smtp, imap = FakeSMTP(), FakeIMAP()
    rc, salida = correr_envio(args + ["--tope", "40"], capsys, imap=lambda u, p: imap, smtp=lambda u, p: smtp)
    assert rc == 0 and len(smtp.enviados) == 1 and len(imap.appends) == 1
    assert "tope diario" in salida["creados"][0]["motivo_borrador"]


def test_corte_de_smtp_a_mitad_no_reenvia_al_reintentar(entorno, capsys):
    args, registro, _ = entorno
    rc, salida = correr_envio(args, capsys, smtp=lambda u, p: FakeSMTP(fallar_en=1))
    assert rc == 1 and "Re-ejecutá" in salida["errores"][0]
    assert leer_estados(registro) == {"info@hotel0.ch": "enviado"}
    smtp = FakeSMTP()
    rc, salida = correr_envio(args, capsys, smtp=lambda u, p: smtp)
    assert rc == 0 and [to for to, _ in smtp.enviados] == [["info@hotel1.ch"]]


def test_dry_run_con_enviar_no_conecta(entorno, capsys):
    args, registro, _ = entorno
    rc, salida = correr_envio(args + ["--dry-run"], capsys)
    assert rc == 0 and len(salida["enviados"]) == 2 and not registro.exists()
