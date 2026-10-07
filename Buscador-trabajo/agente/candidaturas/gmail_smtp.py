"""Envío por SMTP de Gmail.

Es el ÚNICO módulo del agente que envía mails, y solo lo usa `crear_borradores.py --enviar`
con mensajes del lote del día que ya pasaron todas las validaciones (CV del catálogo y de 1 página,
un solo destinatario, lugar no contactado, firma presente).
"""
import smtplib
from email.message import EmailMessage


class ErrorEnvio(RuntimeError):
    pass


def conectar(usuario: str, password: str) -> smtplib.SMTP_SSL:
    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60)
    smtp.login(usuario, password)
    return smtp


def enviar(smtp, mensaje: EmailMessage, para: str) -> None:
    rechazados = smtp.send_message(mensaje, to_addrs=[para])
    if rechazados:
        raise ErrorEnvio(f"Gmail rechazó el destinatario: {rechazados}")
