"""Paso 2: depuración de los controles en papel contra Workflow y la agenda.

Para cada control indicado en papel se decide si sigue en lista de espera:

* EN WORKFLOW   – el mismo control ya está registrado en Workflow (misma fecha ±1 día).
* REEMPLAZADA   – el paciente tiene un comprobante en papel más reciente.
* ATENDIDA      – tuvo una atención posterior de la misma especialidad (agenda) o una
                  atención posterior registrada en Workflow.
* AGENDADA      – tiene una cita futura de la misma especialidad.

Todo se compara dentro de la especialidad del control (ver especialidades.py):
un control de traumatología no se da por atendido con una cita de cardiología.
* NO REQUIERE   – la indicación dice alta, ingreso a LEQ o comprobante anulado.
* PENDIENTE     – nada de lo anterior (incluye citados que no se atendieron).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from .comprobante import apellidos_primero, run_valido
from .especialidades import CATALOGO_BASE, Catalogo, normalizar
from .plazo import es_nsp, interpretar_plazo, no_requiere_control, proximo_control

EN_LISTA = {"PENDIENTE", "AGENDADA"}


@dataclass
class Control:
    run: str
    fecha: datetime
    nombre: str
    profesional: str
    local: str
    especialidad: str = ""
    indicacion: str = ""
    anotaciones: str = ""
    archivo: str = ""
    pagina: int | None = None
    copias: list[str] = field(default_factory=list)
    meses: int | None = None
    mes: str | None = None
    proximo: datetime | None = None
    criterio: str = ""
    observacion: str = ""
    # resultado del cruce
    estado: str = ""
    resultado: str = ""
    fecha_posterior: datetime | None = None
    prof_posterior: str = ""
    fuente: str = ""
    cobertura: str = ""
    detalle_citas: str = ""


def _puntaje(f: dict) -> int:
    return len(str(f.get("Indicación manuscrita") or "")) + len(str(f.get("Anotaciones de contacto") or ""))


def _tokens(t: str) -> set[str]:
    return {w for w in re.split(r"[^A-Z]+", _norm_espacios(t)) if len(w) > 2}


def _norm_espacios(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t or "") if not unicodedata.combining(c)).upper()


def nombre_profesional(impreso: str, nombres_workflow: list[str]) -> str:
    """El comprobante trae 'Pedro Pablo Soto Rojas'; Workflow 'SOTO ROJAS PEDRO PABLO'.
    Se usa el nombre de Workflow cuyas palabras están todas en el impreso (o al revés)."""
    tp = _tokens(impreso)
    mejor, puntos = impreso, 1
    for w in nombres_workflow:
        tw = _tokens(w)
        if len(tw) >= 2 and (tw <= tp or tp <= tw) and len(tw & tp) > puntos:
            mejor, puntos = w, len(tw & tp)
    return mejor


def armar_controles(filas: list[dict], catalogo: Catalogo | None = None,
                    especialidad_por_defecto: str = "") -> tuple[list[Control], list[dict]]:
    """Agrupa copias del mismo comprobante (mismo RUN y fecha) y calcula el
    próximo control. Devuelve los controles y las filas descartadas por datos
    incompletos (sin RUN o sin fecha).

    La especialidad sale de la planilla de revisión; si falta, se deduce del
    Local y, en último caso, se usa ``especialidad_por_defecto``."""
    catalogo = catalogo or CATALOGO_BASE
    grupos: dict[tuple, list[dict]] = {}
    incompletas = []
    for f in filas:
        if not f.get("run") or not f.get("fecha"):
            incompletas.append(f)
            continue
        grupos.setdefault((f["run"], f["fecha"]), []).append(f)
    controles = []
    for (run, fecha), fs in grupos.items():
        b = max(fs, key=_puntaje)
        ind = str(b.get("Indicación manuscrita") or "").strip()
        anot = str(b.get("Anotaciones de contacto") or "").strip()
        meses, mes = b.get("Plazo (meses)"), b.get("Mes indicado (AAAA-MM)")
        meses = int(meses) if str(meses or "").strip().isdigit() else None
        mes = str(mes).strip()[:7] if mes else None
        if not meses and not mes:
            meses, mes = interpretar_plazo(ind, fecha)
        prox, criterio = proximo_control(fecha, meses, mes)
        obs = ["Digitalizado desde comprobante en papel"]
        if not ind:
            obs.append("sin indicación manuscrita de control")
        if es_nsp(ind + " " + anot):
            obs.append("NSP (no se presentó)")
        if "(?)" in ind:
            obs.append("manuscrito de lectura dudosa")
        if b.get("Fecha citación corregida"):
            obs.append("fecha de atención corregida a mano en el papel")
        if not run_valido(run):
            obs.append("RUT no valida dígito verificador (verificar)")
        nombre = b["nombre"] if len(b["nombre"].split()) >= 2 else ""
        esp = (b.get("especialidad") or catalogo.de_texto(str(b.get("Local") or ""))
               or especialidad_por_defecto.upper())
        if not esp:
            obs.append("especialidad no reconocida (completar 'Especialidad corregida')")
        controles.append(Control(
            run=run, fecha=fecha, nombre=apellidos_primero(nombre), profesional=str(b.get("Profesional") or ""),
            local=str(b.get("Local") or ""), especialidad=esp, indicacion=ind, anotaciones=anot, archivo=str(b.get("Archivo") or ""),
            pagina=b.get("Página"), copias=[x["ID"] for x in fs if x is not b], meses=meses, mes=mes,
            proximo=prox, criterio=criterio, observacion="; ".join(obs)))
    controles.sort(key=lambda c: (c.especialidad, c.profesional, c.fecha, c.nombre))
    return controles, incompletas


def _motivo(c: pd.Series) -> str:
    m = c.get("Motivo No Atención") if c.get("Estado Cita") == "NO ATENDIDO" else c.get("Motivo Cancelación")
    return f" ({m})" if isinstance(m, str) and m.strip() and m != "nan" else ""


def cruzar(controles: list[Control], workflow: pd.DataFrame | None, agenda: pd.DataFrame | None,
           hoy: datetime | None = None, catalogo: Catalogo | None = None) -> list[Control]:
    hoy = hoy or datetime.now()
    catalogo = catalogo or CATALOGO_BASE
    wf = workflow if workflow is not None else pd.DataFrame(
        columns=["Rut Paciente", "Fecha Atención", "Profesional", "Especialidad"])
    wf_con_esp = "Especialidad" in wf.columns
    wf = wf.assign(_esp=wf["Especialidad"].map(normalizar) if wf_con_esp else "")
    wf_por_clave = {k: g for k, g in wf.groupby(["Rut Paciente", "_esp"])}
    wf_por_run = {r: g for r, g in wf.groupby("Rut Paciente")}
    if agenda is not None and len(agenda):
        ag = agenda.assign(_esp=agenda["Agenda"].astype(str).map(lambda a: normalizar(catalogo.de_texto(a))))
        ag = ag.sort_values("fc")
        inicio_agenda = agenda["fc"].min()
        fin_agenda = agenda["fc"].max()
    else:
        ag, inicio_agenda, fin_agenda = pd.DataFrame(columns=["RUT Paciente", "fc", "_esp", "Agenda"]), None, None
    ag_por_run = {r: g for r, g in ag.groupby("RUT Paciente")}
    fechas_por_clave: dict[tuple, list[datetime]] = {}
    for c in controles:
        fechas_por_clave.setdefault((c.run, normalizar(c.especialidad)), []).append(c.fecha)

    # Profesionales con la misma ortografía que Workflow
    nombres_wf = list(wf["Profesional"].dropna().unique()) if "Profesional" in wf else []
    # Especialidad con la misma ortografía que Workflow ("NEUROCIRUGIA" -> "NEUROCIRUGÍA" o al revés)
    esp_wf = {normalizar(e): e for e in wf["Especialidad"].dropna().unique()} if "Especialidad" in wf else {}

    for c in controles:
        c.profesional = nombre_profesional(c.profesional, nombres_wf)
        c.especialidad = esp_wf.get(normalizar(c.especialidad), c.especialidad)
        if inicio_agenda is None:
            c.cobertura = "sin reportes de agenda"
        elif c.fecha < inicio_agenda:
            c.cobertura = f"parcial: agenda revisada desde {inicio_agenda:%d/%m/%Y}"
        else:
            c.cobertura = f"completa hasta {fin_agenda:%d/%m/%Y}"
        esp = normalizar(c.especialidad)
        nombre_esp = c.especialidad.lower() or "la especialidad"
        # Sin especialidad conocida se compara con todo (criterio más amplio).
        g_wf = wf_por_clave.get((c.run, esp)) if esp and wf_con_esp else wf_por_run.get(c.run)
        mismo = []
        despues = []
        if g_wf is not None:
            for _, w in g_wf.iterrows():
                fa = w["Fecha Atención"]
                if pd.isna(fa):
                    continue
                if abs((fa - c.fecha).days) <= 1:
                    mismo.append(w)
                elif fa > c.fecha + timedelta(days=1):
                    despues.append(w)
        citas = ag_por_run.get(c.run)
        if citas is not None:
            citas = citas[citas["_esp"] == esp] if esp else citas[citas["Agenda"].astype(str) == c.local]
        post = citas[citas["fc"] > c.fecha] if citas is not None else pd.DataFrame(columns=["fc", "Estado Cita"])
        c.detalle_citas = " ; ".join(f"{x.fc:%d/%m/%Y} {x['Estado Cita']}{_motivo(x)} - {x['Agenda']}"
                                     for _, x in post.iterrows())
        atendidas = post[post["Estado Cita"] == "ATENDIDO"]
        futuras = post[(post["Estado Cita"] == "AGENDADO") & (post["fc"] >= pd.Timestamp(hoy.date()))]
        mas_recientes = [f for f in fechas_por_clave[(c.run, esp)] if f > c.fecha]

        if mismo:
            c.estado, c.resultado, c.fuente = "EN WORKFLOW", "Ya registrado en Workflow (no agregar)", "Workflow"
        elif mas_recientes:
            c.estado, c.resultado = "REEMPLAZADA", "Reemplazado por indicación posterior en papel"
        elif len(atendidas):
            a = atendidas.iloc[0]
            c.estado, c.resultado, c.fuente = "ATENDIDA", "ATENDIDO", "Reporte agenda"
            c.fecha_posterior, c.prof_posterior = a["fc"].to_pydatetime(), str(a["Nombre Profesional"])
        elif despues:
            w = sorted(despues, key=lambda x: x["Fecha Atención"])[0]
            c.estado, c.resultado, c.fuente = "ATENDIDA", "ATENDIDO", "Workflow (nueva atención con control indicado)"
            c.fecha_posterior, c.prof_posterior = w["Fecha Atención"].to_pydatetime(), str(w["Profesional"])
        elif len(futuras):
            f = futuras.iloc[0]
            c.estado, c.resultado, c.fuente = "AGENDADA", f"Agendado (cita futura de {nombre_esp})", "Reporte agenda"
            c.fecha_posterior, c.prof_posterior = f["fc"].to_pydatetime(), str(f["Nombre Profesional"])
            c.observacion += f"; cita de {nombre_esp} agendada el {f['fc']:%d/%m/%Y}"
        elif len(post):
            c.estado, c.resultado, c.fuente = "PENDIENTE", "Citado pero no atendido (NSP/cancelada/bloqueada)", "Reporte agenda"
            c.observacion += "; citado sin atención: " + c.detalle_citas
        else:
            c.estado, c.resultado = "PENDIENTE", "Sin cita posterior registrada"
            if inicio_agenda is not None:
                desde = max(inicio_agenda, c.fecha)
                c.observacion += f"; sin control de {nombre_esp} registrado desde {desde:%d/%m/%Y}"
        if c.estado == "PENDIENTE" and no_requiere_control(c.indicacion):
            c.estado, c.resultado = "NO REQUIERE", "No requiere control (alta / ingreso a LEQ / cita anulada)"
        if c.estado in EN_LISTA and g_wf is not None and not mismo:
            fechas = sorted(x for x in g_wf["Fecha Atención"] if not pd.isna(x))
            if fechas:
                c.observacion += f"; paciente también tiene control en Workflow (atención {fechas[0]:%d/%m/%Y})"
    return controles
