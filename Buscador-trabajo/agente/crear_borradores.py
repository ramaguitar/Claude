"""Procesa el lote diario de candidaturas: lo valida y crea borradores en Gmail o, con --enviar, los envía.

Con --enviar, cada mail se envía por SMTP espaciado al azar, hasta el tope diario. Quedan como borrador:
los que llevan un CV traducido pendiente de aprobación (cvs_pendientes.json) y los que exceden el tope.
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from candidaturas import gmail_imap, gmail_smtp
from candidaturas.lote import cargar_catalogo, cargar_lote, validar
from candidaturas.mensaje import construir_mensaje
from candidaturas.registro import Registro, dominio

AGENTE = Path(__file__).resolve().parent
BASE = AGENTE.parent
TOPE_DIARIO = 40
PAUSA_MIN, PAUSA_MAX = 45, 90


def _resumen(m: dict, motivo_borrador: str | None = None) -> dict:
    r = {"lugar": m["lugar"], "zona": m["zona"], "email": m["email"], "puesto": m["puesto"], "cv": m["cv"]}
    if motivo_borrador:
        r["motivo_borrador"] = motivo_borrador
    return r


def cargar_pendientes(ruta: Path) -> set[str]:
    return set(json.loads(ruta.read_text(encoding="utf-8"))) if ruta.exists() else set()


def main(argv=None, conectar=gmail_imap.conectar, conectar_smtp=gmail_smtp.conectar, dormir=time.sleep) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("lote", type=Path)
    p.add_argument("--enviar", action="store_true", help="enviar en lugar de dejar en borradores")
    p.add_argument("--tope", type=int, default=TOPE_DIARIO, help="máximo de mails enviados por día")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--registro", type=Path, default=AGENTE / "contactados.csv")
    p.add_argument("--env", type=Path, default=AGENTE / ".env")
    p.add_argument("--catalogo", type=Path, default=AGENTE / "cvs.json")
    p.add_argument("--pendientes", type=Path, default=AGENTE / "cvs_pendientes.json")
    a = p.parse_args(argv)

    load_dotenv(a.env)
    usuario = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    resultado = {"lote": str(a.lote), "dry_run": a.dry_run, "enviados": [], "creados": [],
                 "salteados": [], "errores": []}

    def salir(codigo: int) -> int:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return codigo

    if not a.dry_run and not (usuario and password):
        resultado["errores"].append("Faltan GMAIL_USER o GMAIL_APP_PASSWORD en agente/.env")
        return salir(2)

    try:
        # antes de tocar Gmail: si no se puede registrar, re-ejecutar duplicaría mails
        if not a.dry_run:
            Registro.verificar_escritura(a.registro)
        registro = Registro(a.registro)
    except (OSError, ValueError) as e:
        resultado["errores"].append(
            f"No se puede usar el registro contactados.csv ({e}). ¿Está abierto en Excel? Cerralo y re-ejecutá.")
        return salir(2)
    validos, resultado["salteados"] = validar(cargar_lote(a.lote), registro, a.base, cargar_catalogo(a.catalogo))
    remitente = f"Ramiro Guitar <{usuario or 'ramiroguitar28@gmail.com'}>"
    mensajes = [(m, construir_mensaje(m, remitente, a.base, a.lote.stem)) for m in validos]

    # reparto: qué se envía y qué queda en borrador (y por qué)
    a_enviar, a_borrador = [], []
    if a.enviar:
        pendientes = cargar_pendientes(a.pendientes)
        cupo = max(0, a.tope - registro.enviados_el(date.today().isoformat()))
        for m, msg in mensajes:
            if m["cv"] in pendientes:
                a_borrador.append((m, msg, "CV traducido pendiente de aprobación"))
            elif len(a_enviar) < cupo:
                a_enviar.append((m, msg))
            else:
                a_borrador.append((m, msg, f"tope diario de {a.tope} envíos alcanzado"))
    else:
        a_borrador = [(m, msg, None) for m, msg in mensajes]

    if a.dry_run:
        resultado["enviados"] = [_resumen(m) for m, _ in a_enviar]
        resultado["creados"] = [_resumen(m, motivo) for m, _, motivo in a_borrador]
        return salir(0)

    def registrar(m: dict, estado: str) -> bool:
        try:
            registro.agregar({**m, "fecha": date.today().isoformat(), "dominio": dominio(m["email"]),
                              "vacante_url": m.get("vacante_url") or "", "estado": estado})
            return True
        except OSError as e:
            resultado["errores"].append(
                f"El mail para {m['email']} quedó {estado} pero no se pudo registrar en contactados.csv ({e}). "
                "NO re-ejecutes el lote: duplicaría mails. Hay que agregar a mano esa fila al registro.")
            return False

    # 1) borradores
    if a_borrador:
        try:
            imap = conectar(usuario, password)
        except Exception as e:
            resultado["errores"].append(f"No se pudo conectar a Gmail: {e}")
            return salir(1)
        try:
            carpeta = gmail_imap.carpeta_borradores(imap)
            for m, msg, motivo in a_borrador:
                gmail_imap.guardar_borrador(imap, carpeta, msg)
                resultado["creados"].append(_resumen(m, motivo))
                # se registra apenas se crea: si Gmail corta después, re-ejecutar no duplica
                if not registrar(m, "borrador"):
                    return salir(3)
        except Exception as e:
            resultado["errores"].append(
                f"Gmail cortó a mitad del lote: {e}. Re-ejecutá el mismo comando: los ya procesados se saltean.")
            return salir(1)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    # 2) envíos, espaciados al azar para no parecer un envío masivo
    if a_enviar:
        try:
            smtp = conectar_smtp(usuario, password)
        except Exception as e:
            resultado["errores"].append(f"No se pudo conectar al envío de Gmail (SMTP): {e}")
            return salir(1)
        try:
            for i, (m, msg) in enumerate(a_enviar):
                if i > 0:
                    dormir(random.uniform(PAUSA_MIN, PAUSA_MAX))
                gmail_smtp.enviar(smtp, msg, m["email"])
                resultado["enviados"].append(_resumen(m))
                if not registrar(m, "enviado"):
                    return salir(3)
        except Exception as e:
            resultado["errores"].append(
                f"Gmail cortó a mitad del envío: {e}. Re-ejecutá el mismo comando: los ya enviados se saltean.")
            return salir(1)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    return salir(0)


if __name__ == "__main__":
    sys.exit(main())
