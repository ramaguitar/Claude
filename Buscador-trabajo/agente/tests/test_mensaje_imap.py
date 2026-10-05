import email
from email import policy

import pytest

from candidaturas import gmail_imap
from candidaturas.mensaje import construir_mensaje, message_id, nombre_adjunto

FIRMA = "Ramiro Guitar\n+33 7 45 23 48 84\nramiroguitar28@gmail.com"


@pytest.fixture
def base(tmp_path):
    (tmp_path / "CVs").mkdir()
    (tmp_path / "CVs" / "cv.pdf").write_bytes(b"%PDF-1.4 contenido-cv")
    return tmp_path


def un_mail():
    return {"email": "info@hotel-alpin.ch", "idioma": "de", "cv": "CVs/cv.pdf",
            "asunto": "Bewerbung für die Wintersaison 2026/27 – «Saas-Fee»",
            "cuerpo": "Sehr geehrte Damen und Herren\n\nFreundliche Grüsse, ça va, però\n\n" + FIRMA}


def test_mensaje_conserva_acentos_y_adjunta_cv(base):
    msg = construir_mensaje(un_mail(), "Ramiro Guitar <ramiroguitar28@gmail.com>", base, "2026-10-06")
    vuelta = email.message_from_bytes(msg.as_bytes(), policy=policy.default)
    assert vuelta["Subject"] == "Bewerbung für die Wintersaison 2026/27 – «Saas-Fee»"
    assert vuelta["To"] == "info@hotel-alpin.ch"
    assert "Freundliche Grüsse, ça va, però" in vuelta.get_body(("plain",)).get_content()
    adjuntos = list(vuelta.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "CV-RamiroGuitar-DE.pdf"
    assert adjuntos[0].get_content_type() == "application/pdf"
    assert adjuntos[0].get_content() == b"%PDF-1.4 contenido-cv"


def test_message_id_deterministico():
    assert message_id("2026-10-06", "a@b.ch") == message_id("2026-10-06", "a@b.ch")
    assert message_id("2026-10-06", "a@b.ch") != message_id("2026-10-06", "c@b.ch")
    assert nombre_adjunto("ca") == "CV-RamiroGuitar-CA.pdf"


class FakeIMAP:
    def __init__(self, carpetas):
        self.carpetas = carpetas
        self.appends = []

    def list(self):
        return "OK", self.carpetas

    def append(self, carpeta, flags, fecha, datos):
        self.appends.append((carpeta, flags, datos))
        return "OK", [b"APPEND completed"]


def test_detecta_borradores_en_cuenta_en_espanol():
    imap = FakeIMAP([rb'(\HasNoChildren) "/" "INBOX"',
                     rb'(\HasNoChildren \Sent) "/" "[Gmail]/Enviados"',
                     rb'(\Drafts \HasNoChildren) "/" "[Gmail]/Borradores"'])
    assert gmail_imap.carpeta_borradores(imap) == '"[Gmail]/Borradores"'


def test_sin_carpeta_borradores_da_error_claro():
    with pytest.raises(gmail_imap.ErrorGmail, match="IMAP"):
        gmail_imap.carpeta_borradores(FakeIMAP([rb'(\HasNoChildren) "/" "INBOX"']))


def test_guardar_borrador_usa_flag_draft(base):
    imap = FakeIMAP([])
    msg = construir_mensaje(un_mail(), "Ramiro Guitar <ramiroguitar28@gmail.com>", base, "2026-10-06")
    gmail_imap.guardar_borrador(imap, '"[Gmail]/Borradores"', msg)
    carpeta, flags, datos = imap.appends[0]
    assert carpeta == '"[Gmail]/Borradores"' and flags == r"(\Draft)"
    assert b"CV-RamiroGuitar-DE.pdf" in datos
