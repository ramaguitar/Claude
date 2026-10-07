"""Genera un CV en PDF a partir de un contenido JSON y una de las plantillas HTML (housekeeping / especifico)."""
import base64
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

PLANTILLAS = Path(__file__).resolve().parent / "plantillas_cv"
NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
ESCALAS = (1.0, 0.97, 0.94, 0.91, 0.88, 0.85)
TIPOS = {"parrafo", "experiencia", "lista"}
OBLIGATORIOS = ("plantilla", "puesto", "idioma", "nombre", "contacto", "secciones")


def cargar_contenido(ruta: Path) -> dict:
    c = json.loads(Path(ruta).read_text(encoding="utf-8"))
    faltan = [k for k in OBLIGATORIOS if not c.get(k)]
    if faltan:
        raise ValueError(f"Faltan campos en el contenido: {', '.join(faltan)}")
    if c["plantilla"] not in {"especifico", "housekeeping"}:
        raise ValueError(f"Plantilla desconocida: {c['plantilla']}")
    for s in c["secciones"]:
        if s.get("tipo") not in TIPOS:
            raise ValueError(f"Tipo de sección desconocido: {s.get('tipo')}")
    return c


def _inline(texto: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(texto, quote=False))


def _seccion(s: dict) -> str:
    if s["tipo"] == "parrafo":
        cuerpo = f'<p class="parrafo">{_inline(s["texto"])}</p>'
    elif s["tipo"] == "experiencia":
        cuerpo = "".join(
            f'<div class="exp"><div class="puesto">{_inline(it["puesto"])}</div>'
            f'<div class="detalle">{_inline(it["detalle"])}</div>'
            f'<ul>{"".join(f"<li>{_inline(b)}</li>" for b in it.get("bullets", []))}</ul></div>'
            for it in s["items"])
    else:
        clase = "con-vinetas" if s.get("vinetas", True) else "sin-vinetas"
        cuerpo = f'<ul class="{clase}">' + "".join(f"<li>{_inline(i)}</li>" for i in s["items"]) + "</ul>"
    return f'<section><h2>{_inline(s["titulo"])}</h2>{cuerpo}</section>'


def _data_uri(foto: Path) -> str:
    mime = "image/png" if Path(foto).suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(Path(foto).read_bytes()).decode("ascii")


def a_html(contenido: dict, foto: Path, escala: float = 1.0) -> str:
    plantilla = (PLANTILLAS / f'{contenido["plantilla"]}.html').read_text(encoding="utf-8")
    titular = f'<div class="titular">{_inline(contenido["titular"])}</div>' if contenido.get("titular") else ""
    reemplazos = {
        "{{IDIOMA}}": html.escape(contenido["idioma"]),
        "{{ESCALA}}": f"{escala:.2f}",
        "{{FOTO}}": _data_uri(foto),
        "{{NOMBRE}}": _inline(contenido["nombre"]),
        "{{TITULAR}}": titular,
        "{{CONTACTO}}": _inline(contenido["contacto"]),
        "{{SECCIONES}}": "".join(_seccion(s) for s in contenido["secciones"]),
    }
    for clave, valor in reemplazos.items():
        plantilla = plantilla.replace(clave, valor)
    return plantilla


def buscar_navegador() -> Path:
    for c in NAVEGADORES:
        if Path(c).is_file():
            return Path(c)
    for nombre in ("chrome", "msedge", "chromium"):
        encontrado = shutil.which(nombre)
        if encontrado:
            return Path(encontrado)
    raise FileNotFoundError("No se encontró Chrome ni Edge para generar el PDF")


def html_a_pdf(html_txt: str, salida: Path, navegador: Path | None = None) -> None:
    navegador = navegador or buscar_navegador()
    salida = Path(salida).resolve()
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        fuente = Path(tmp) / "cv.html"
        fuente.write_text(html_txt, encoding="utf-8")
        subprocess.run([str(navegador), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tmp) / 'perfil'}", f"--print-to-pdf={salida}",
                        fuente.as_uri()], check=True, capture_output=True, timeout=120)
    if not salida.is_file():
        raise RuntimeError(f"El navegador no generó {salida}")


def paginas(pdf: Path) -> int:
    with pymupdf.open(pdf) as d:
        return d.page_count


def previsualizar(pdf: Path, png: Path, dpi: int = 110) -> None:
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as d:
        d[0].get_pixmap(dpi=dpi).save(png)


def renderizar(contenido: dict, foto: Path, salida: Path, png: Path | None = None,
               navegador: Path | None = None) -> dict:
    for escala in ESCALAS:
        html_a_pdf(a_html(contenido, foto, escala), salida, navegador)
        n = paginas(salida)
        if n == 1:
            break
    png = Path(png) if png else Path(salida).with_suffix(".png")
    previsualizar(salida, png)
    if n != 1:
        # un CV de varias páginas no debe quedar disponible para adjuntarse; la vista previa sí queda
        Path(salida).unlink(missing_ok=True)
    return {"pdf": str(salida), "png": str(png), "escala": escala, "paginas": n, "ok": n == 1}
