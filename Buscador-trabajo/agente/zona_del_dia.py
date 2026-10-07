"""Decide en qué zonas trabaja hoy el agente, según la rotación semanal por país (rotacion.json).

Orden de la lista: primero el país del día (su zona en curso, después sus pendientes en el orden de
zonas.json); si ese país se agota, los demás países según la prioridad. Las zonas cubiertas no entran.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

AGENTE = Path(__file__).resolve().parent
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def zonas_del_dia(zonas: list[dict], rotacion: dict, fecha: date) -> dict:
    pais = rotacion["por_dia"][DIAS[fecha.weekday()]]
    orden_paises = [pais] + [p for p in rotacion["prioridad"] if p != pais]
    lista = []
    for p in orden_paises:
        del_pais = [z for z in zonas if z["pais"] == p and z["estado"] != "cubierta"]
        del_pais.sort(key=lambda z: z["estado"] != "en_curso")  # estable: la en curso primero
        lista += [{"nombre": z["nombre"], "pais": z["pais"], "idioma": z["idioma"], "estado": z["estado"]}
                  for z in del_pais]
    return {"fecha": fecha.isoformat(), "pais_del_dia": pais, "zonas": lista}


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zonas", type=Path, default=AGENTE / "zonas.json")
    p.add_argument("--rotacion", type=Path, default=AGENTE / "rotacion.json")
    p.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    a = p.parse_args(argv)
    zonas = json.loads(a.zonas.read_text(encoding="utf-8"))
    rotacion = json.loads(a.rotacion.read_text(encoding="utf-8"))
    print(json.dumps(zonas_del_dia(zonas, rotacion, a.fecha), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
