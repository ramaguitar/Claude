"""Carga y validación del lote diario de candidaturas."""
import json
import re
from pathlib import Path

import pymupdf

from .registro import DOMINIOS_GENERICOS, Registro, dominio, normalizar_email

CAMPOS_OBLIGATORIOS = ("zona", "lugar", "tipo", "web", "email", "idioma", "puesto", "cv", "asunto", "cuerpo")
IDIOMAS = frozenset({"fr", "de", "it", "ca", "en", "es"})
RE_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
RE_MARCADOR = re.compile(r"\{[^}]*\}|\[[^\]]*\]|XXX|TODO")
FIRMA_OBLIGATORIA = "ramiroguitar28@gmail.com"


def cargar_lote(ruta: Path) -> list[dict]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(datos, list):
        raise ValueError("El lote debe ser una lista JSON de mails")
    return datos


def _paginas(pdf: Path) -> int | None:
    try:
        with pymupdf.open(pdf) as d:
            return d.page_count
    except Exception:
        return None


def cargar_catalogo(ruta: Path) -> set[str]:
    """Rutas de CV permitidas: las que figuran en cvs.json."""
    catalogo = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return {r for por_idioma in catalogo.values() for r in por_idioma.values()}


def _problema(mail: dict, base_dir: Path, cvs_permitidos: set[str]) -> str | None:
    faltan = [c for c in CAMPOS_OBLIGATORIOS if not str(mail.get(c) or "").strip()]
    if faltan:
        return "faltan campos: " + ", ".join(faltan)
    email = normalizar_email(mail["email"])
    if not RE_EMAIL.match(email):
        return f"email inválido: {mail['email']}"
    if mail["idioma"] not in IDIOMAS:
        return f"idioma desconocido: {mail['idioma']}"
    # solo se adjuntan CVs del catálogo: nunca un PDF cualquiera del disco
    if mail["cv"] not in cvs_permitidos:
        return f"CV fuera del catálogo cvs.json: {mail['cv']}"
    cv = Path(base_dir) / mail["cv"]
    if cv.suffix.lower() != ".pdf" or not cv.is_file():
        return f"CV inexistente: {mail['cv']}"
    n = _paginas(cv)
    if n != 1:
        return f"CV con {n} páginas (debe tener 1): {mail['cv']}" if n else f"CV ilegible: {mail['cv']}"
    for campo in ("asunto", "cuerpo"):
        m = RE_MARCADOR.search(mail[campo])
        if m:
            return f"marcador sin completar en {campo}: {m.group(0)}"
    if FIRMA_OBLIGATORIA not in mail["cuerpo"]:
        return "el cuerpo no tiene la firma"
    return None


def validar(mails: list[dict], registro: Registro, base_dir: Path,
            cvs_permitidos: set[str]) -> tuple[list[dict], list[dict]]:
    validos, salteados = [], []
    vistos_emails: set[str] = set()
    vistos_dominios: set[str] = set()
    for mail in mails:
        motivo = _problema(mail, base_dir, cvs_permitidos)
        if motivo is None:
            email = normalizar_email(mail["email"])
            d = dominio(email)
            motivo = registro.motivo_contactado(email)
            if motivo is None and (email in vistos_emails
                                   or (d not in DOMINIOS_GENERICOS and d in vistos_dominios)):
                motivo = f"repetido dentro del lote: {email}"
        if motivo:
            salteados.append({"lugar": mail.get("lugar", ""), "email": mail.get("email", ""), "motivo": motivo})
            continue
        vistos_emails.add(email)
        if d not in DOMINIOS_GENERICOS:
            vistos_dominios.add(d)
        validos.append({**mail, "email": email})
    return validos, salteados
