"""Lectura de las fuentes para el cruce: planilla de revisión, lista de
controles de Workflow y reportes de agenda de Experto."""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from .comprobante import run_valido

COLUMNAS_AGENDA = ["RUT Paciente", "Nombre Paciente", "Agenda", "Nombre Profesional", "Fecha Cita",
                   "Hora Cita", "Estado Cita", "Motivo Cancelación", "Motivo No Atención"]
COLUMNAS_WORKFLOW = ["Fecha Atención", "Próximo Control", "Indicaciones", "Rut Paciente", "Paciente",
                     "Especialidad", "Profesional", "Local", "Observación", "Agenda otorgada",
                     "Fecha control", "Hora control"]


def _fecha(valor) -> datetime | None:
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        return valor
    try:
        return datetime.strptime(str(valor).strip()[:10], "%d/%m/%Y")
    except ValueError:
        try:
            return datetime.strptime(str(valor).strip()[:10], "%Y-%m-%d")
        except ValueError:
            return None


def leer_revision(ruta: Path) -> list[dict]:
    ws = load_workbook(ruta, data_only=True)["Revisión"]
    cab = [c.value for c in ws[1]]
    filas = []
    for valores in ws.iter_rows(min_row=2, values_only=True):
        d = dict(zip(cab, valores))
        if not d.get("ID") or str(d.get("Excluir (S/N)") or "").strip().upper().startswith("S"):
            continue
        d["run"] = str(d.get("RUN corregido") or d.get("RUN") or "").strip().upper().replace(".", "")
        d["nombre"] = str(d.get("Nombre corregido") or d.get("Nombre") or "").strip().upper()
        d["fecha"] = _fecha(d.get("Fecha citación corregida")) or _fecha(d.get("Fecha citación"))
        d["especialidad"] = str(d.get("Especialidad corregida") or d.get("Especialidad") or "").strip().upper()
        filas.append(d)
    return filas


def leer_workflow(ruta: Path) -> pd.DataFrame:
    df = pd.read_excel(ruta, dtype={"Rut Paciente": str})
    falta = [c for c in COLUMNAS_WORKFLOW if c not in df.columns]
    if falta:
        raise ValueError(f"{ruta.name}: no tiene las columnas de Workflow {falta}")
    df = df[COLUMNAS_WORKFLOW].copy()
    df["Rut Paciente"] = df["Rut Paciente"].astype(str).str.upper().str.replace(".", "", regex=False)
    for c in ("Fecha Atención", "Próximo Control", "Fecha control"):
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df


def _buscar_cabecera(df: pd.DataFrame) -> int | None:
    for i in range(min(30, len(df))):
        if "RUT Paciente" in [str(v).strip() for v in df.iloc[i].tolist()]:
            return i
    return None


def _soffice() -> str | None:
    for c in ("soffice", "libreoffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice",
              r"C:\Program Files\LibreOffice\program\soffice.exe"):
        if shutil.which(c) or Path(c).exists():
            return shutil.which(c) or c
    return None


def _convertir_con_libreoffice(ruta: Path) -> pd.DataFrame | None:
    """Algunos .xls de Experto vienen dañados; LibreOffice (si está instalado) los lee igual."""
    soffice = _soffice()
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "csv:Text - txt - csv (StarCalc):44,34,76",
                            "--outdir", tmp, str(ruta)], capture_output=True, timeout=600, check=False)
            csv = next(Path(tmp).glob("*.csv"), None)
            return pd.read_csv(csv, header=None, dtype=str) if csv else None
        except (subprocess.SubprocessError, OSError, ValueError):
            return None


def _leer_un_reporte(ruta: Path) -> pd.DataFrame | None:
    suf = ruta.suffix.lower()
    if ruta.stat().st_size < 1000:
        return None  # descargas vacías ("Página no encontrada")
    if suf == ".csv":
        for sep in (";", ","):
            try:
                df = pd.read_csv(ruta, sep=sep, dtype=str, encoding="utf-8-sig",
                                 usecols=lambda c: c in COLUMNAS_AGENDA)
                if "RUT Paciente" in df.columns:
                    return df
            except (ValueError, UnicodeDecodeError):
                continue
        return None
    # .xls/.xlsx de Experto (a veces es HTML con extensión .xls)
    crudo = None
    for motor in ("calamine", None):
        try:
            crudo = pd.read_excel(ruta, header=None, dtype=str, engine=motor)
            break
        except BaseException:  # noqa: BLE001 - calamine puede abortar con archivos dañados
            crudo = None
    if crudo is None:
        crudo = _convertir_con_libreoffice(ruta)
    if crudo is None:
        try:
            tablas = pd.read_html(io.StringIO(ruta.read_text(encoding="latin-1", errors="ignore")))
            crudo = max(tablas, key=len).astype(str)
            crudo = pd.concat([crudo.columns.to_frame().T, crudo], ignore_index=True)
        except (ValueError, ImportError):
            return None
    fila = _buscar_cabecera(crudo)
    if fila is None:
        return None
    df = crudo.iloc[fila + 1:].copy()
    df.columns = [str(c).strip() for c in crudo.iloc[fila]]
    return df[[c for c in COLUMNAS_AGENDA if c in df.columns]]


def leer_agenda(rutas: list[Path], ruts: set[str] | None = None, avisar=print) -> pd.DataFrame:
    """Lee reportes de agenda (carpetas o archivos). Si se entregan RUT, sólo
    conserva las citas de esos pacientes (ahorra memoria)."""
    archivos: list[Path] = []
    for r in rutas:
        if r.is_dir():
            archivos += sorted(p for p in r.rglob("*") if p.suffix.lower() in {".xls", ".xlsx", ".csv"})
        elif r.exists():
            archivos.append(r)
    partes, omitidos = [], []
    for a in archivos:
        df = _leer_un_reporte(a)
        if df is None or df.empty:
            omitidos.append(a.name)
            continue
        df["RUT Paciente"] = df["RUT Paciente"].astype(str).str.upper().str.replace(".", "", regex=False)
        if ruts is not None:
            df = df[df["RUT Paciente"].isin(ruts)]
        partes.append(df)
    if omitidos:
        avisar(f"⚠ {len(omitidos)} archivo(s) de agenda vacíos o ilegibles (se omiten): "
               + ", ".join(omitidos[:5]) + (" …" if len(omitidos) > 5 else ""))
    if not partes:
        return pd.DataFrame(columns=COLUMNAS_AGENDA + ["fc"])
    a = pd.concat(partes, ignore_index=True)
    a["fc"] = pd.to_datetime(a["Fecha Cita"], dayfirst=True, errors="coerce")
    a = a.dropna(subset=["fc"]).drop_duplicates(["RUT Paciente", "fc", "Hora Cita", "Agenda"])
    avisar(f"Agenda: {len(archivos) - len(omitidos)} archivo(s), {len(a)} citas de los pacientes, "
           f"del {a['fc'].min():%d/%m/%Y} al {a['fc'].max():%d/%m/%Y}")
    return a


def runs_de(filas: list[dict]) -> set[str]:
    return {f["run"] for f in filas if f.get("run") and re.fullmatch(r"\d{6,8}-[\dK]", f["run"])}


__all__ = ["leer_revision", "leer_workflow", "leer_agenda", "runs_de", "run_valido"]
