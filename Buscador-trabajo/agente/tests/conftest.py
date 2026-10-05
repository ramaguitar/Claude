import pymupdf
import pytest


@pytest.fixture
def hacer_pdf():
    """Crea un PDF real con la cantidad de páginas pedida."""
    def _hacer(ruta, paginas=1):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open() as d:
            for _ in range(paginas):
                d.new_page()
            d.save(ruta)
        return ruta
    return _hacer
