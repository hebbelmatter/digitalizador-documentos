"""Pruebas con datos ficticios (RUT y nombres inventados)."""

from datetime import datetime

import pandas as pd

from controles.comprobante import apellidos_primero, contar_comprobantes, leer_comprobante, run_valido
from controles.cruce import armar_controles, cruzar, nombre_profesional
from controles.especialidades import Catalogo, especialidad_de
from controles.plazo import interpretar_plazo, no_requiere_control, proximo_control

TEXTO = """HOSPITAL CARLOS VAN BUREN
COMPROBANTE DE CITACION
Nombre Paciente: JUAN ANDRES PEREZ ROJAS i
RUN: 11.111.111-1 Ficha: 123
Citación: 21/01/2025 Hora: 12:00:00
Local: HCVB-CC-NEUROC. COLUMNA COMPLEJA
Profesional: Pedro Pablo Soto Rojas   Unidad
"""


def test_leer_comprobante():
    c = leer_comprobante(TEXTO)
    assert c.run == "11111111-1" and c.run_valido
    assert c.nombre == "JUAN ANDRES PEREZ ROJAS"
    assert c.fecha_citacion == "21/01/2025" and c.hora == "12:00"
    assert c.local == "HCVB-CC-NEUROC. COLUMNA COMPLEJA"
    assert c.profesional == "PEDRO PABLO SOTO ROJAS"


def test_run_y_nombres():
    assert run_valido("12345678-5") and not run_valido("12345678-9")
    assert apellidos_primero("JUAN ANDRES PEREZ ROJAS") == "PEREZ ROJAS JUAN ANDRES"
    assert contar_comprobantes(TEXTO + TEXTO) == 2


def test_plazos():
    f = datetime(2025, 11, 10)
    assert interpretar_plazo("Control 3 meses con RNM", f) == (3, None)
    assert interpretar_plazo("1 año", f) == (12, None)
    assert interpretar_plazo("30-60 días con EMG", f) == (1, None)
    assert interpretar_plazo("Abril 2026", f) == (None, "2026-04")
    assert interpretar_plazo("Febrero", f) == (None, "2026-02")
    assert interpretar_plazo("Control con lo solicitado", f) == (None, None)
    assert proximo_control(f, 3, None)[0] == datetime(2026, 2, 10)
    assert no_requiere_control("De alta") and no_requiere_control("Ingreso a LEQ")
    assert not no_requiere_control("Control 3 meses")


def test_nombre_profesional():
    wf = ["SOTO ROJAS PEDRO PABLO", "MUNOZ VERA LUIS"]
    assert nombre_profesional("PEDRO PABLO SOTO ROJAS IF", wf) == wf[0]
    assert nombre_profesional("MUNOZ TAPIA JORGE LUIS", wf) == "MUNOZ TAPIA JORGE LUIS"


def _fila(fid, run, fecha, ind="", local="HCVB-CC-NEUROCIRUGIA"):
    return {"ID": fid, "Archivo": "x.pdf", "Página": 1, "run": run, "nombre": "ANA MARIA SOTO PEREZ",
            "fecha": fecha, "Profesional": "DOCTOR PRUEBA UNO", "Local": local,
            "Indicación manuscrita": ind}


def test_cruce():
    filas = [
        _fila("a", "11111111-1", datetime(2025, 3, 1), "3 meses"),  # atendida después
        _fila("b", "22222222-2", datetime(2025, 3, 1), "6 meses"),  # sin citas: pendiente
        _fila("c", "33333333-3", datetime(2025, 3, 1), "1 mes"),    # ya en Workflow
        _fila("d", "44444444-4", datetime(2024, 1, 1), "2 meses"),  # reemplazada por "e"
        _fila("e", "44444444-4", datetime(2025, 5, 1), "De alta"),  # no requiere
        _fila("f", "55555555-5", datetime(2025, 3, 1), "3 meses"),  # cita futura
        _fila("f2", "55555555-5", datetime(2025, 3, 1), "3 meses con RNM"),  # copia de "f"
    ]
    controles, incompletas = armar_controles(filas)
    assert len(controles) == 6 and not incompletas
    workflow = pd.DataFrame({"Rut Paciente": ["33333333-3"], "Fecha Atención": [pd.Timestamp(2025, 3, 2)],
                             "Profesional": ["PRUEBA UNO DOCTOR"]})
    agenda = pd.DataFrame({
        "RUT Paciente": ["11111111-1", "55555555-5"],
        "Agenda": ["HCVB-CC-NEUROCIRUGIA", "HCVB-CC-NEUROCIRUGIA"],
        "Nombre Profesional": ["X", "Y"],
        "fc": [pd.Timestamp(2025, 6, 1), pd.Timestamp(2026, 12, 1)],
        "Estado Cita": ["ATENDIDO", "AGENDADO"],
    })
    cruzar(controles, workflow, agenda, hoy=datetime(2026, 11, 18))
    estado = {(c.run, c.fecha.year): c.estado for c in controles}
    assert estado[("11111111-1", 2025)] == "ATENDIDA"
    assert estado[("22222222-2", 2025)] == "PENDIENTE"
    assert estado[("33333333-3", 2025)] == "EN WORKFLOW"
    assert estado[("44444444-4", 2024)] == "REEMPLAZADA"
    assert estado[("44444444-4", 2025)] == "NO REQUIERE"
    assert estado[("55555555-5", 2025)] == "AGENDADA"
    # el profesional se escribe como en Workflow
    assert {c.profesional for c in controles} == {"PRUEBA UNO DOCTOR"}


def test_especialidades():
    assert especialidad_de("HCVB-CC-NEUROC. ONCOLOGICA") == "NEUROCIRUGÍA"
    assert especialidad_de("HCVB-CC-NC LUMBAGO ALTA RESOLUTIVIDAD") == "NEUROCIRUGÍA"
    assert especialidad_de("HCVB-CC-NEUROLOGIA ADULTO") == "NEUROLOGÍA"
    assert especialidad_de("HCVB-CC-UROLOGIA") == "UROLOGÍA"
    assert especialidad_de("HCVB-CC-TRAUMATOLOGIA RODILLA") == "TRAUMATOLOGÍA"
    assert especialidad_de("HCVB-CC-ONCOLOGIA MEDICA") == "ONCOLOGÍA"
    assert especialidad_de("HCVB-CC-CIRUGIA DIGESTIVA") == "CIRUGÍA"
    assert especialidad_de("HCVB-CC-ALGO DESCONOCIDO") == ""
    propio = Catalogo([("CIRUGÍA DE MAMA", r"MAMA")] + [])
    assert propio.de_texto("HCVB-CC-PATOLOGIA MAMARIA") == "CIRUGÍA DE MAMA"


def test_local_no_catalogado():
    t = TEXTO.replace("HCVB-CC-NEUROC. COLUMNA COMPLEJA", "HCVB-CC-TRAUMATOLOGIA RODILLA")
    assert leer_comprobante(t).local == "HCVB-CC-TRAUMATOLOGIA RODILLA"


def test_cruce_por_especialidad():
    trauma = "HCVB-CC-TRAUMATOLOGIA RODILLA"
    filas = [
        _fila("a", "11111111-1", datetime(2025, 3, 1), "3 meses", local=trauma),
        _fila("b", "11111111-1", datetime(2025, 2, 1), "6 meses"),  # neurocirugía, mismo paciente
    ]
    controles, _ = armar_controles(filas)
    assert {c.especialidad for c in controles} == {"TRAUMATOLOGÍA", "NEUROCIRUGÍA"}
    agenda = pd.DataFrame({
        "RUT Paciente": ["11111111-1"], "Agenda": ["HCVB-CC-CARDIOLOGIA"], "Nombre Profesional": ["X"],
        "fc": [pd.Timestamp(2025, 6, 1)], "Estado Cita": ["ATENDIDO"],
    })
    workflow = pd.DataFrame({"Rut Paciente": ["11111111-1"], "Fecha Atención": [pd.Timestamp(2025, 3, 1)],
                             "Profesional": ["OTRO"], "Especialidad": ["CARDIOLOGÍA"]})
    cruzar(controles, workflow, agenda, hoy=datetime(2026, 11, 18))
    # La cita y el control de cardiología no cuentan; el papel de trauma no reemplaza al de neurocirugía.
    assert {c.especialidad: c.estado for c in controles} == {"TRAUMATOLOGÍA": "PENDIENTE",
                                                              "NEUROCIRUGÍA": "PENDIENTE"}


def test_digitalizar_por_partes(tmp_path, monkeypatch):
    """Agregar PDF en varias vueltas conserva lo anterior y omite lo ya leído."""
    from pathlib import Path

    from controles import digitalizar as dg

    leidos = []

    def filas_falsas(doc, n_pag, img, *a):
        leidos.append(doc.name)
        return [{"ID": f"{doc.stem}|{n_pag}|1", "Archivo": doc.name, "Página": n_pag, "RUN": "11111111-1"}]

    monkeypatch.setattr(dg.ocr, "configurar_tesseract", lambda: None)
    monkeypatch.setattr(dg.cargar, "cargar_paginas", lambda doc, dpi: [None, None])
    monkeypatch.setattr(dg, "_filas_de_pagina", filas_falsas)
    salida = tmp_path / "salida"
    monkeypatch.setattr(dg.cargar, "listar_documentos", lambda e: [Path("a.pdf")])
    dg.digitalizar(Path("x"), salida, avisar=lambda *_: None)
    monkeypatch.setattr(dg.cargar, "listar_documentos", lambda e: [Path("a.pdf"), Path("b.pdf")])
    dg.digitalizar(Path("x"), salida, avisar=lambda *_: None)
    assert leidos == ["a.pdf", "a.pdf", "b.pdf", "b.pdf"]  # "a.pdf" no se volvió a leer
    ids = [f["ID"] for f in dg._leer_revision_existente(salida / "revision.xlsx").values()]
    assert ids == ["a|1|1", "a|2|1", "b|1|1", "b|2|1"]
