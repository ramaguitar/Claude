"""Importa a contactados.csv los destinatarios de mails ya enviados (estado enviado_manual)."""
import argparse
import json
import sys
from pathlib import Path

from candidaturas.registro import Registro, importar_enviados

AGENTE = Path(__file__).resolve().parent


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("enviados", type=Path, help="JSON: lista de {email, fecha, asunto}")
    p.add_argument("--registro", type=Path, default=AGENTE / "contactados.csv")
    a = p.parse_args(argv)
    enviados = json.loads(a.enviados.read_text(encoding="utf-8"))
    n = importar_enviados(Registro(a.registro), enviados)
    print(json.dumps({"importados": n, "recibidos": len(enviados)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
