"""Escritura de los Excel finales.

* ``Controles_papel_digitalizados.xlsx``: Resumen, Digitalizados (todos),
  Lista de espera, Cruce atenciones y Detalle digitalización.
* ``Lista_espera_controles_CONSOLIDADA.xlsx``: Workflow + controles en papel
  pendientes, con la columna Origen y un resumen con fórmulas.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from .cruce import EN_LISTA, Control
from .fuentes import COLUMNAS_WORKFLOW

FMT_FECHA = "DD/MM/YYYY"


def _formato(ws: Worksheet, anchos: list[int], col_fechas: tuple[int, ...] = ()) -> None:
    for i, fila in enumerate(ws.iter_rows()):
        for celda in fila:
            celda.font = Font(name="Calibri", size=11, bold=(i == 0))
            if i and (celda.column - 1 in col_fechas or isinstance(celda.value, datetime)):
                celda.number_format = FMT_FECHA
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = ancho
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _fila_workflow(c: Control) -> list:
    if c.estado == "AGENDADA":
        agenda, fecha_ctrl = "AGENDADA", c.fecha_posterior
    elif c.estado == "ATENDIDA":
        agenda, fecha_ctrl = "ATENDIDA", c.fecha_posterior
    else:
        agenda, fecha_ctrl = c.estado, None
    return [c.fecha, c.proximo, c.indicacion or None, c.run, c.nombre, c.especialidad or None, c.profesional,
            c.local, c.observacion, agenda, fecha_ctrl, None]


def escribir_digitalizados(controles: list[Control], destino: Path, incompletas: list[dict] | None = None) -> Path:
    wb = Workbook()
    resumen = wb.active
    resumen.title = "Resumen"

    dig = wb.create_sheet("Digitalizados")
    dig.append(COLUMNAS_WORKFLOW + ["Resultado del cruce", "¿En lista de espera?", "Archivo origen", "Página",
                                    "Anotaciones de contacto"])
    for c in controles:
        dig.append(_fila_workflow(c) + [c.resultado, "SÍ" if c.estado in EN_LISTA else "NO", c.archivo, c.pagina,
                                        c.anotaciones or None])
    _formato(dig, [14, 15, 42, 14, 34, 16, 34, 32, 55, 16, 14, 12, 40, 12, 30, 8, 60], (0, 1, 10))

    en_lista = [c for c in controles if c.estado in EN_LISTA]
    le = wb.create_sheet(f"Lista de espera ({len(en_lista)})")
    le.append(COLUMNAS_WORKFLOW)
    for c in en_lista:
        le.append(_fila_workflow(c))
    _formato(le, [14, 15, 42, 14, 34, 16, 34, 32, 60, 16, 14, 12], (0, 1, 10))

    cr = wb.create_sheet("Cruce atenciones")
    cr.append(["Rut Paciente", "Paciente", "Profesional", "Fecha Atención (papel)", "Próximo Control (papel)",
               "Resultado", "¿En lista de espera real?", "Fecha atención posterior", "Profesional atención posterior",
               "Fuente", "Cobertura del cruce", "Citas posteriores de la especialidad (reportes)"])
    for c in controles:
        cr.append([c.run, c.nombre, c.profesional, c.fecha, c.proximo, c.resultado,
                   "SÍ" if c.estado in EN_LISTA else "NO", c.fecha_posterior, c.prof_posterior or None,
                   c.fuente or None, c.cobertura, c.detalle_citas or None])
    _formato(cr, [14, 36, 30, 14, 14, 42, 12, 14, 30, 26, 34, 80], (3, 4, 7))

    de = wb.create_sheet("Detalle digitalización")
    de.append(["Rut Paciente", "Paciente", "Fecha Atención", "Archivo", "Página", "Otras copias escaneadas",
               "Indicación manuscrita", "Criterio Próximo Control", "Anotaciones de contacto"])
    for c in controles:
        de.append([c.run, c.nombre, c.fecha, c.archivo, c.pagina, ", ".join(c.copias) or None,
                   c.indicacion or None, c.criterio, c.anotaciones or None])
    _formato(de, [14, 36, 14, 30, 8, 22, 50, 32, 70], (2,))

    if incompletas:
        inc = wb.create_sheet("Sin RUN o sin fecha")
        inc.append(["ID", "Archivo", "Página", "RUN leído", "Nombre", "Fecha citación", "Indicación manuscrita"])
        for f in incompletas:
            inc.append([f.get("ID"), f.get("Archivo"), f.get("Página"), f.get("run"), f.get("nombre"),
                        f.get("Fecha citación"), f.get("Indicación manuscrita")])
        _formato(inc, [30, 30, 8, 14, 34, 14, 50])

    _resumen_digitalizados(resumen, dig.max_row, Counter(c.especialidad for c in controles),
                           Counter(c.profesional for c in controles))
    wb.save(destino)
    return destino


def _resumen_digitalizados(rs: Worksheet, n: int, especialidades: Counter, profesionales: Counter) -> None:
    L = "Digitalizados!"
    rs.append(["Controles en papel digitalizados"])
    rs.append([f"Generado el {datetime.now():%d/%m/%Y %H:%M}"])
    rs.append(["Indicador", "Valor"])
    rs.append(["Registros digitalizados", f"=COUNTA({L}D2:D{n})"])
    rs.append(["Pacientes distintos", f"=SUMPRODUCT(1/COUNTIF({L}D2:D{n},{L}D2:D{n}))"])
    rs.append(["En lista de espera (SÍ)", f'=COUNTIF({L}N2:N{n},"SÍ")'])
    rs.append([])
    rs.append(["Agenda otorgada", "Registros"])
    ini = rs.max_row + 1
    for estado in ["PENDIENTE", "AGENDADA", "EN WORKFLOW", "ATENDIDA", "REEMPLAZADA", "NO REQUIERE"]:
        r = rs.max_row + 1
        rs.append([estado, f"=COUNTIF({L}J2:J{n},A{r})"])
    r = rs.max_row + 1
    rs.append(["Total", f"=SUM(B{ini}:B{r - 1})"])
    rs.append([])
    rs.append(["Especialidad", "Digitalizados", "En lista de espera"])
    ini_e = rs.max_row + 1
    for esp, _ in especialidades.most_common():
        r = rs.max_row + 1
        rs.append([esp or "(sin especialidad)", f'=COUNTIF({L}F2:F{n},"{esp}")' if esp else f'=COUNTBLANK({L}F2:F{n})',
                   f'=COUNTIFS({L}F2:F{n},"{esp}",{L}N2:N{n},"SÍ")' if esp
                   else f'=COUNTIFS({L}F2:F{n},"",{L}N2:N{n},"SÍ")'])
    r_e = rs.max_row + 1
    rs.append(["Total", f"=SUM(B{ini_e}:B{r_e - 1})", f"=SUM(C{ini_e}:C{r_e - 1})"])
    rs.append([])
    rs.append(["Profesional", "Digitalizados", "En lista de espera"])
    ini2 = rs.max_row + 1
    for prof, _ in profesionales.most_common():
        r = rs.max_row + 1
        rs.append([prof, f"=COUNTIF({L}G2:G{n},A{r})", f'=COUNTIFS({L}G2:G{n},A{r},{L}N2:N{n},"SÍ")'])
    r = rs.max_row + 1
    rs.append(["Total", f"=SUM(B{ini2}:B{r - 1})", f"=SUM(C{ini2}:C{r - 1})"])
    for fila in rs.iter_rows():
        for c in fila:
            c.font = Font(name="Calibri", size=11, bold=c.row in {1, 3, 8, ini + 6, ini_e - 1, r_e, ini2 - 1, r})
    rs.column_dimensions["A"].width = 42
    rs.column_dimensions["B"].width = 16
    rs.column_dimensions["C"].width = 18


def escribir_consolidado(controles: list[Control], workflow: pd.DataFrame, destino: Path, nombre_workflow: str) -> Path:
    filas = []
    for _, w in workflow.iterrows():
        v = [None if pd.isna(x) else (x.to_pydatetime() if isinstance(x, pd.Timestamp) else x) for x in w.tolist()]
        filas.append(v + ["Workflow"])
    for c in controles:
        if c.estado in EN_LISTA:
            filas.append(_fila_workflow(c) + ["Papel (digitalizado)"])
    filas.sort(key=lambda f: (f[0] or datetime(1900, 1, 1), f[4] or ""))

    wb = Workbook()
    rs = wb.active
    rs.title = "Resumen"
    ws = wb.create_sheet("Lista de espera consolidada")
    ws.append(COLUMNAS_WORKFLOW + ["Origen"])
    for f in filas:
        ws.append(f)
    _formato(ws, [14, 15, 40, 14, 34, 16, 34, 32, 60, 16, 14, 12, 20], (0, 1, 10))
    n = ws.max_row
    L = "'Lista de espera consolidada'!"
    rs.append(["Lista de espera de controles – consolidada"])
    rs.append([f"Fuentes: Workflow ({nombre_workflow}) + comprobantes en papel depurados con la agenda"])
    rs.append([])
    rs.append(["Origen", "PENDIENTE", "AGENDADA", "Total"])
    for o in ["Workflow", "Papel (digitalizado)"]:
        r = rs.max_row + 1
        rs.append([o, f'=COUNTIFS({L}$M$2:$M${n},A{r},{L}$J$2:$J${n},"PENDIENTE")',
                   f'=COUNTIFS({L}$M$2:$M${n},A{r},{L}$J$2:$J${n},"AGENDADA")', f"=B{r}+C{r}"])
    r = rs.max_row + 1
    rs.append(["Total", f"=SUM(B5:B{r - 1})", f"=SUM(C5:C{r - 1})", f"=SUM(D5:D{r - 1})"])
    rs.append([])
    rs.append(["Especialidad", "Workflow", "Papel", "Total"])
    ini_e = rs.max_row + 1
    for esp, _ in Counter(f[5] for f in filas if f[5]).most_common():
        r = rs.max_row + 1
        rs.append([esp, f'=COUNTIFS({L}$F$2:$F${n},A{r},{L}$M$2:$M${n},"Workflow")',
                   f'=COUNTIFS({L}$F$2:$F${n},A{r},{L}$M$2:$M${n},"Papel (digitalizado)")', f"=B{r}+C{r}"])
    r_e = rs.max_row + 1
    rs.append(["Total", f"=SUM(B{ini_e}:B{r_e - 1})", f"=SUM(C{ini_e}:C{r_e - 1})", f"=SUM(D{ini_e}:D{r_e - 1})"])
    rs.append([])
    rs.append(["Profesional", "Workflow", "Papel", "Total"])
    ini = rs.max_row + 1
    for prof, _ in Counter(f[6] for f in filas).most_common():
        r = rs.max_row + 1
        rs.append([prof, f'=COUNTIFS({L}$G$2:$G${n},A{r},{L}$M$2:$M${n},"Workflow")',
                   f'=COUNTIFS({L}$G$2:$G${n},A{r},{L}$M$2:$M${n},"Papel (digitalizado)")', f"=B{r}+C{r}"])
    r = rs.max_row + 1
    rs.append(["Total", f"=SUM(B{ini}:B{r - 1})", f"=SUM(C{ini}:C{r - 1})", f"=SUM(D{ini}:D{r - 1})"])
    for fila in rs.iter_rows():
        for c in fila:
            c.font = Font(name="Calibri", size=11, bold=c.row in {1, 4, 7, ini_e - 1, r_e, ini - 1, r})
    rs.column_dimensions["A"].width = 42
    for col in "BCD":
        rs.column_dimensions[col].width = 14
    wb.save(destino)
    return destino
