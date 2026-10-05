"""Registro de lugares contactados (contactados.csv) y reglas de deduplicación."""
import csv
from pathlib import Path

COLUMNAS = ["fecha", "zona", "lugar", "tipo", "email", "dominio", "web", "puesto",
            "cv", "idioma", "vacante_url", "asunto", "estado"]

# Proveedores de correo compartidos por muchos negocios: solo se deduplica el email exacto.
DOMINIOS_GENERICOS = frozenset({
    "gmail.com", "googlemail.com", "outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr",
    "hotmail.ch", "hotmail.it", "live.com", "live.fr", "yahoo.com", "yahoo.fr", "yahoo.it",
    "icloud.com", "me.com", "orange.fr", "wanadoo.fr", "free.fr", "sfr.fr", "laposte.net",
    "bluewin.ch", "gmx.ch", "gmx.de", "gmx.net", "gmx.at", "web.de", "libero.it", "tiscali.it",
    "virgilio.it", "alice.it", "andorra.ad", "protonmail.com", "proton.me",
    # dominios de estación que alojan el correo de varios negocios del pueblo
    "verbier.ch",
})


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def dominio(email: str) -> str:
    return normalizar_email(email).rsplit("@", 1)[-1]


class Registro:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.emails: set[str] = set()
        self.dominios: set[str] = set()
        self.columnas = list(COLUMNAS)
        if self.ruta.exists() and self.ruta.stat().st_size > 0:
            with self.ruta.open(encoding="utf-8-sig", newline="") as f:
                lector = csv.DictReader(f)
                if lector.fieldnames:
                    self.columnas = list(lector.fieldnames)
                for fila in lector:
                    if fila.get("email"):
                        self._recordar(fila["email"])

    def _recordar(self, email: str) -> None:
        e = normalizar_email(email)
        self.emails.add(e)
        d = dominio(e)
        if d not in DOMINIOS_GENERICOS:
            self.dominios.add(d)

    def motivo_contactado(self, email: str) -> str | None:
        e = normalizar_email(email)
        if e in self.emails:
            return f"email ya contactado: {e}"
        d = dominio(e)
        if d not in DOMINIOS_GENERICOS and d in self.dominios:
            return f"dominio ya contactado: {d}"
        return None

    def agregar(self, fila: dict) -> None:
        fila = dict(fila)
        fila["email"] = normalizar_email(fila["email"])
        if not fila.get("dominio"):
            fila["dominio"] = dominio(fila["email"])
        nuevo = not self.ruta.exists() or self.ruta.stat().st_size == 0
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        # utf-8-sig solo al crear: deja el BOM al inicio para que Excel lea bien los acentos
        with self.ruta.open("a", encoding="utf-8-sig" if nuevo else "utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.columnas, extrasaction="ignore", restval="")
            if nuevo:
                w.writeheader()
            w.writerow(fila)
        self._recordar(fila["email"])


def importar_enviados(registro: Registro, enviados: list[dict]) -> int:
    """Agrega como 'enviado_manual' los destinatarios que todavía no están en el registro."""
    n = 0
    for e in enviados:
        email = normalizar_email(e.get("email", ""))
        if "@" not in email or email in registro.emails:
            continue
        registro.agregar({"fecha": e.get("fecha", ""), "email": email,
                          "asunto": e.get("asunto", ""), "estado": "enviado_manual"})
        n += 1
    return n
