"""Construcción del mensaje MIME de cada candidatura."""
import hashlib
import html
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path


def nombre_adjunto(idioma: str) -> str:
    return f"CV-RamiroGuitar-{idioma.upper()}.pdf"


def message_id(fecha_lote: str, email: str) -> str:
    h = hashlib.sha256(f"{fecha_lote}|{email}".encode()).hexdigest()[:24]
    return f"<{h}.candidatura@ramiroguitar.local>"


def cuerpo_html(cuerpo: str) -> str:
    """Un <p> por párrafo (separados por línea en blanco); los saltos simples pasan a <br>."""
    parrafos = [p.strip("\n") for p in cuerpo.replace("\r\n", "\n").split("\n\n") if p.strip()]
    html_parrafos = "".join(f"<p>{html.escape(p, quote=False).replace(chr(10), '<br>')}</p>" for p in parrafos)
    return f"<html><body>{html_parrafos}</body></html>"


def construir_mensaje(mail: dict, remitente: str, base_dir: Path, fecha_lote: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = remitente
    msg["To"] = mail["email"]
    msg["Subject"] = mail["asunto"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = message_id(fecha_lote, mail["email"])
    msg.set_content(mail["cuerpo"], charset="utf-8")
    # versión HTML: sin ella, Gmail envía el texto plano cortado a ~70 caracteres por línea
    msg.add_alternative(cuerpo_html(mail["cuerpo"]), subtype="html", charset="utf-8")
    datos = (Path(base_dir) / mail["cv"]).read_bytes()
    msg.add_attachment(datos, maintype="application", subtype="pdf",
                       filename=nombre_adjunto(mail["idioma"]))
    return msg
