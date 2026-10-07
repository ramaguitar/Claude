"""Acceso IMAP a Gmail limitado a localizar la carpeta de borradores y guardar borradores.

Este módulo no envía mails: no hay SMTP ni ningún comando de envío.
"""
import imaplib
import re
import time
from email.message import EmailMessage

RE_LIST = re.compile(r'^\((?P<flags>[^)]*)\) "(?P<sep>[^"]*)" (?P<nombre>.+)$')


class ErrorGmail(RuntimeError):
    pass


def conectar(usuario: str, password: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(usuario, password)
    return imap


def carpeta_borradores(imap) -> str:
    typ, datos = imap.list()
    if typ != "OK":
        raise ErrorGmail(f"LIST falló: {typ}")
    for linea in datos:
        texto = linea.decode("utf-8", "replace") if isinstance(linea, bytes) else str(linea)
        m = RE_LIST.match(texto)
        if m and r"\Drafts" in m.group("flags").split():
            nombre = m.group("nombre").strip()
            return nombre if nombre.startswith('"') else f'"{nombre}"'
    raise ErrorGmail(r"No se encontró la carpeta de borradores (\Drafts). ¿Está IMAP habilitado en Gmail?")


def guardar_borrador(imap, carpeta: str, mensaje: EmailMessage) -> None:
    typ, datos = imap.append(carpeta, r"(\Draft)", imaplib.Time2Internaldate(time.time()), mensaje.as_bytes())
    if typ != "OK":
        raise ErrorGmail(f"APPEND falló: {typ} {datos}")
