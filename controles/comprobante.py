"""Lectura de los campos impresos de un "Comprobante de citación" de Experto
(RUN, nombre, fecha y hora de citación, local de atención y profesional)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from digitalizador.extraccion import digito_verificador

# Locales conocidos: palabra clave -> nombre exacto en Experto. Sirven para
# corregir errores de OCR en el nombre del local; un local que no esté aquí se
# usa tal como se leyó. Se pueden agregar locales de cualquier especialidad.
# El orden importa: se usa el primero que aparezca en la línea "Local".
LOCALES: list[tuple[str, str]] = [
    ("LUMBAGO", "HCVB-CC-NC LUMBAGO ALTA RESOLUTIVIDAD"),
    ("COLUMNA", "HCVB-CC-NEUROC. COLUMNA COMPLEJA"),
    ("INFANT", "HCVB-CC-NEUROCIR INFANTIL"),
    ("HIPOFISIS", "HCVB-CC-NEUROC. PAT. HIPOFISIS"),
    ("VASCULAR", "HCVB-CC-NEUROC. VASCULAR"),
    ("ONCOLOG", "HCVB-CC-NEUROC. ONCOLOGICA"),
    ("OPERATIVO", "HCVB-CC-OPERATIVO NEUROCIRUGIA"),
    ("ADULTO", "HCVB-CC-NEUROCIR ADULTO"),
    ("NEUROCIRUGIA", "HCVB-CC-NEUROCIRUGIA"),
]

_RE_RUN = re.compile(r"RUN[:;.,]?\s*([0-9]{1,2}\.?[0-9]{3}\.?[0-9]{3})\s*[-‐–]\s*([0-9Kk])")
_RE_NOMBRE = re.compile(r"Nombre\s*Pac\w*[:;.]?\s*([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ' \-]+[A-ZÁÉÍÓÚÑÜ])")
_RE_CITACION = re.compile(r"Citaci.n[:;.]?\D{0,8}(\d{2}/\d{2}/\d{4})", re.I)
_RE_HORA = re.compile(r"\b(\d{2}:\d{2}):\d{2}\b")
_RE_LOCAL = re.compile(r"Local[:;.]?\s*(HCVB.{0,50})", re.I)
_RE_PROFESIONAL = re.compile(r"Profesional[:;.|\s]*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{6,60})", re.I)
_RE_PALABRA = re.compile(r"^[A-ZÁÉÍÓÚÑÜ\-']+$")


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))


def normalizar_run(cuerpo: str, dv: str) -> str:
    """'12.345.678', 'k' -> '12345678-K' (formato de Workflow)."""
    numero = int(re.sub(r"\D", "", cuerpo))
    return f"{numero}-{dv.upper()}"


def run_valido(run: str) -> bool:
    m = re.fullmatch(r"(\d{6,8})-([\dK])", (run or "").upper())
    return bool(m) and digito_verificador(int(m.group(1))) == m.group(2)


@dataclass
class Comprobante:
    run: str = ""
    run_valido: bool = False
    nombre: str = ""
    fecha_citacion: str = ""  # dd/mm/aaaa
    hora: str = ""
    local: str = ""
    profesional: str = ""
    teleconsulta: bool = False
    runs_leidos: list[str] = field(default_factory=list)


def _limpiar_nombre(nombre: str) -> str:
    palabras = nombre.split()
    # El OCR suele pegar basura al final del nombre ("PEREZ ROJAS i Blo").
    while palabras and (not _RE_PALABRA.match(palabras[-1]) or (len(palabras[-1]) <= 2 and palabras[-1] not in {"DE", "DEL", "LA"})):
        palabras.pop()
    return " ".join(palabras)


def _local(textos: list[str]) -> str:
    leido = ""
    for t in textos:
        m = _RE_LOCAL.search(t)
        if m:
            linea = sin_tildes(m.group(1)).upper()
            for clave, nombre in LOCALES:
                if clave in linea:
                    return nombre
            linea = re.split(r"\s{2,}|PROFESIONAL|FECHA|UNIDAD|\|", linea)[0]
            linea = re.sub(r"[^A-Z0-9 .\-]", "", linea).strip(" .-")
            if len(linea) > len(leido):
                leido = linea
    if leido:
        return leido
    todo = sin_tildes(" ".join(textos)).upper()
    for clave, nombre in LOCALES[:6]:  # sólo las palabras claves específicas
        if clave in todo:
            return nombre
    return ""


def _profesional(textos: list[str]) -> str:
    for t in textos:
        for m in _RE_PROFESIONAL.finditer(t):
            nombre = re.split(r"\s{2,}|Unidad|Local|Fecha", m.group(1))[0].strip()
            if len(nombre.split()) >= 2:
                return sin_tildes(nombre).upper()
    return ""


def leer_comprobante(*textos: str) -> Comprobante:
    """Extrae los campos de uno o más textos OCR de la misma página
    (p. ej. la página completa y un recorte de la zona de datos)."""
    c = Comprobante()
    runs = []
    for t in textos:
        for m in _RE_RUN.finditer(t):
            runs.append(normalizar_run(m.group(1), m.group(2)))
    c.runs_leidos = list(dict.fromkeys(runs))
    validos = [r for r in c.runs_leidos if run_valido(r)]
    c.run = validos[0] if validos else (c.runs_leidos[0] if c.runs_leidos else "")
    c.run_valido = bool(validos)

    nombres = [m.group(1) for t in textos for m in [_RE_NOMBRE.search(t)] if m]
    c.nombre = _limpiar_nombre(max(nombres, key=len)) if nombres else ""

    for t in textos:
        for m in _RE_CITACION.finditer(t):
            d, mth, y = map(int, m.group(1).split("/"))
            if 1 <= d <= 31 and 1 <= mth <= 12 and 2015 <= y <= 2035:
                c.fecha_citacion = m.group(1)
                break
        if c.fecha_citacion:
            break
    hora = next((m.group(1) for t in textos for m in [_RE_HORA.search(t)] if m), "")
    c.hora = hora
    c.local = _local(list(textos))
    c.profesional = _profesional(list(textos))
    c.teleconsulta = "TELECONSULTA" in sin_tildes(" ".join(textos)).upper()
    return c


def contar_comprobantes(texto: str) -> int:
    """Cuántos comprobantes hay en una página (a veces se escanean dos)."""
    return max(1, len(re.findall(r"COMPROBANTE", texto, re.I)))


def apellidos_primero(nombre: str) -> str:
    """'JUAN ANDRES PEREZ ROJAS' -> 'PEREZ ROJAS JUAN ANDRES' (formato Workflow)."""
    t = nombre.split()
    if len(t) < 3:
        return nombre
    k = 3 if len(t) >= 4 and t[-2] in {"DE", "DEL"} else 2
    return " ".join(t[-k:] + t[:-k])
