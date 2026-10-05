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
def entorno(tmp_path):
    base = tmp_path / "base"
    (base / "CVs").mkdir(parents=True)
    (base / "CVs" / "cv.pdf").write_bytes(b"%PDF-1.4 prueba")
    mails = [{"zona": "Zermatt", "lugar": f"Hotel {i}", "tipo": "hotel", "web": f"https://hotel{i}.ch",
              "email": f"info@hotel{i}.ch", "idioma": "de", "puesto": "Housekeeping", "cv": "CVs/cv.pdf",
              "vacante_url": None, "cv_nuevo": False, "asunto": "Bewerbung für die Wintersaison 2026/27",
              "cuerpo": "Sehr geehrte Damen und Herren\n\n" + FIRMA} for i in range(2)]
    lote = tmp_path / "2026-10-06.json"
    lote.write_text(json.dumps(mails, ensure_ascii=False), encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("GMAIL_USER=ramiroguitar28@gmail.com\nGMAIL_APP_PASSWORD=clave-de-prueba\n", encoding="utf-8")
    registro = tmp_path / "contactados.csv"
    args = [str(lote), "--base", str(base), "--registro", str(registro), "--env", str(env)]
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


def test_ningun_archivo_tiene_codigo_de_envio():
    for py in list(AGENTE.glob("*.py")) + list((AGENTE / "candidaturas").glob("*.py")):
        texto = py.read_text(encoding="utf-8")
        for prohibido in ("smtplib", "send_message", "sendmail"):
            assert prohibido not in texto, f"{py.name} contiene {prohibido}"
