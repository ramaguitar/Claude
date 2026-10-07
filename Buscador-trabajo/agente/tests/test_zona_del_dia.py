import json
from datetime import date

import zona_del_dia

ROTACION = {
    "por_dia": {"lunes": "Suiza", "martes": "Francia", "miercoles": "Suiza", "jueves": "Andorra",
                "viernes": "Suiza", "sabado": "Francia", "domingo": "Italia"},
    "prioridad": ["Suiza", "Francia", "Andorra", "Italia"],
}


def z(nombre, pais, estado="pendiente", idioma="fr"):
    return {"nombre": nombre, "pais": pais, "idioma": idioma, "estado": estado}


ZONAS = [
    z("Val Thorens", "Francia", "en_curso"), z("Courchevel", "Francia", "cubierta"), z("Méribel", "Francia"),
    z("Verbier", "Suiza"), z("Crans-Montana", "Suiza", "en_curso"), z("Zermatt", "Suiza", idioma="de"),
    z("Livigno", "Italia", idioma="it"),
    z("Soldeu", "Andorra", idioma="ca"), z("Pas de la Casa", "Andorra", idioma="ca"),
]


def nombres(res):
    return [x["nombre"] for x in res["zonas"]]


def test_cada_dia_de_la_semana_toca_su_pais():
    # 2026-10-05 fue lunes
    esperados = ["Suiza", "Francia", "Suiza", "Andorra", "Suiza", "Francia", "Italia"]
    for i, pais in enumerate(esperados):
        assert zona_del_dia.zonas_del_dia(ZONAS, ROTACION, date(2026, 10, 5 + i))["pais_del_dia"] == pais


def test_primero_la_zona_en_curso_del_pais_despues_sus_pendientes_sin_cubiertas():
    res = zona_del_dia.zonas_del_dia(ZONAS, ROTACION, date(2026, 10, 6))  # martes: Francia
    assert nombres(res)[:2] == ["Val Thorens", "Méribel"]
    assert "Courchevel" not in nombres(res)


def test_si_el_pais_del_dia_se_agota_sigue_la_prioridad():
    res = zona_del_dia.zonas_del_dia(ZONAS, ROTACION, date(2026, 10, 8))  # jueves: Andorra
    assert nombres(res) == ["Soldeu", "Pas de la Casa",
                            "Crans-Montana", "Verbier", "Zermatt",  # Suiza (en curso primero)
                            "Val Thorens", "Méribel",                # Francia
                            "Livigno"]                               # Italia
    assert res["zonas"][0]["idioma"] == "ca"


def test_cli_lee_los_archivos_y_respeta_la_fecha(tmp_path, capsys):
    zonas, rotacion = tmp_path / "zonas.json", tmp_path / "rotacion.json"
    zonas.write_text(json.dumps(ZONAS, ensure_ascii=False), encoding="utf-8")
    rotacion.write_text(json.dumps(ROTACION), encoding="utf-8")
    rc = zona_del_dia.main(["--zonas", str(zonas), "--rotacion", str(rotacion), "--fecha", "2026-10-11"])
    salida = json.loads(capsys.readouterr().out)
    assert rc == 0 and salida["pais_del_dia"] == "Italia" and salida["zonas"][0]["nombre"] == "Livigno"


def test_rotacion_real_del_agente_es_la_acordada():
    rot = json.loads((zona_del_dia.AGENTE / "rotacion.json").read_text(encoding="utf-8"))
    assert rot == ROTACION
