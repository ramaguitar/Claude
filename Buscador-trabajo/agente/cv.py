"""Herramientas de CV para el agente: render de un contenido JSON a PDF y catálogo cvs.json."""
import argparse
import json
import sys
from pathlib import Path

from candidaturas.cv_render import cargar_contenido, renderizar

AGENTE = Path(__file__).resolve().parent


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalogo", type=Path, default=AGENTE / "cvs.json")
    p.add_argument("--base", type=Path, default=AGENTE.parent)
    p.add_argument("--foto", type=Path, default=AGENTE / "cv" / "foto.png")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("render", help="contenido JSON -> PDF de 1 página + PNG de vista previa")
    r.add_argument("contenido", type=Path)
    r.add_argument("salida", type=Path)
    g = sub.add_parser("registrar", help="agrega (puesto, idioma) -> ruta al catálogo cvs.json")
    g.add_argument("puesto")
    g.add_argument("idioma")
    g.add_argument("ruta", type=Path)
    a = p.parse_args(argv)

    if a.comando == "render":
        contenido = cargar_contenido(a.contenido)
        png = AGENTE / "cv" / "previas" / f'{contenido["puesto"]}-{contenido["idioma"]}.png'
        res = renderizar(contenido, a.foto, a.salida, png=png)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 1

    ruta = a.ruta.resolve()
    if not ruta.is_file():
        print(json.dumps({"error": f"No existe {ruta}"}, ensure_ascii=False))
        return 1
    relativa = ruta.relative_to(a.base.resolve()).as_posix()
    catalogo = json.loads(a.catalogo.read_text(encoding="utf-8")) if a.catalogo.exists() else {}
    catalogo.setdefault(a.puesto, {})[a.idioma] = relativa
    a.catalogo.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"puesto": a.puesto, "idioma": a.idioma, "ruta": relativa}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
