"""Crea en Gmail los borradores del lote diario. NUNCA envía mails."""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from candidaturas import gmail_imap
from candidaturas.lote import cargar_lote, validar
from candidaturas.mensaje import construir_mensaje
from candidaturas.registro import Registro, dominio

AGENTE = Path(__file__).resolve().parent
BASE = AGENTE.parent


def _resumen(m: dict) -> dict:
    return {"lugar": m["lugar"], "zona": m["zona"], "email": m["email"], "puesto": m["puesto"], "cv": m["cv"]}


def main(argv=None, conectar=gmail_imap.conectar) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("lote", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--registro", type=Path, default=AGENTE / "contactados.csv")
    p.add_argument("--env", type=Path, default=AGENTE / ".env")
    a = p.parse_args(argv)

    load_dotenv(a.env)
    usuario = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    resultado = {"lote": str(a.lote), "dry_run": a.dry_run, "creados": [], "salteados": [], "errores": []}

    def salir(codigo: int) -> int:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return codigo

    if not a.dry_run and not (usuario and password):
        resultado["errores"].append("Faltan GMAIL_USER o GMAIL_APP_PASSWORD en agente/.env")
        return salir(2)

    registro = Registro(a.registro)
    validos, resultado["salteados"] = validar(cargar_lote(a.lote), registro, a.base)
    remitente = f"Ramiro Guitar <{usuario or 'ramiroguitar28@gmail.com'}>"
    mensajes = [(m, construir_mensaje(m, remitente, a.base, a.lote.stem)) for m in validos]

    if a.dry_run:
        resultado["creados"] = [_resumen(m) for m, _ in mensajes]
        return salir(0)
    if not mensajes:
        return salir(0)

    try:
        imap = conectar(usuario, password)
    except Exception as e:
        resultado["errores"].append(f"No se pudo conectar a Gmail: {e}")
        return salir(1)
    try:
        carpeta = gmail_imap.carpeta_borradores(imap)
        for m, msg in mensajes:
            gmail_imap.guardar_borrador(imap, carpeta, msg)
            # se registra apenas se crea: si Gmail corta después, re-ejecutar no duplica
            registro.agregar({**m, "fecha": date.today().isoformat(), "dominio": dominio(m["email"]),
                              "vacante_url": m.get("vacante_url") or "", "estado": "borrador"})
            resultado["creados"].append(_resumen(m))
    except Exception as e:
        resultado["errores"].append(
            f"Gmail cortó a mitad del lote: {e}. Re-ejecutá el mismo comando: los ya creados se saltean.")
        return salir(1)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return salir(0)


if __name__ == "__main__":
    sys.exit(main())
