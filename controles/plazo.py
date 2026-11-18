"""Interpretación de la indicación manuscrita del médico: plazo del próximo
control ("3 meses", "30 días", "1 año", "abril 2026") y marcas especiales."""

from __future__ import annotations

import re
from datetime import datetime

from dateutil.relativedelta import relativedelta

from .comprobante import sin_tildes

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_NUMEROS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
            "ocho": 8, "diez": 10, "doce": 12}
_N = r"(\d{1,2}|" + "|".join(_NUMEROS) + r")"
_RE_MESES = re.compile(_N + r"\s*(?:-\s*\d{1,2}\s*)?mes(?:es)?\b")
_RE_DIAS = re.compile(r"(\d{1,3})\s*(?:-\s*\d{1,3}\s*)?d[ií]as?\b")
_RE_SEMANAS = re.compile(_N + r"\s*semanas?\b")
_RE_ANIO = re.compile(r"\b(" + _N[1:-1] + r")\s*a[nñ]os?\b|\banual\b")
_RE_MES_TXT = re.compile(r"\b(" + "|".join(MESES) + r")\b(?:\s*(?:de\s*)?(\d{2,4}))?")


def _num(t: str) -> int:
    return int(t) if t.isdigit() else _NUMEROS[t]


def interpretar_plazo(indicacion: str, fecha_atencion: datetime | None = None) -> tuple[int | None, str | None]:
    """Devuelve (meses, 'AAAA-MM') según lo escrito. Un plazo en meses/días/años
    tiene prioridad sobre un mes nombrado ("3 meses, junio 2026" -> 3 meses)."""
    t = sin_tildes(indicacion or "").lower()
    if not t.strip():
        return None, None
    m = _RE_MESES.search(t)
    if m:
        return _num(m.group(1)), None
    m = _RE_ANIO.search(t)
    if m:
        return (12 * _num(m.group(1)) if m.group(1) else 12), None
    m = _RE_DIAS.search(t)
    if m:
        return max(1, round(int(m.group(1)) / 30)), None
    m = _RE_SEMANAS.search(t)
    if m:
        return max(1, round(_num(m.group(1)) / 4)), None
    m = _RE_MES_TXT.search(t)
    if m:
        mes = MESES[m.group(1)]
        if m.group(2):
            anio = int(m.group(2))
            anio = anio + 2000 if anio < 100 else anio
        elif fecha_atencion:
            anio = fecha_atencion.year + (1 if mes < fecha_atencion.month else 0)
        else:
            return None, None
        return None, f"{anio:04d}-{mes:02d}"
    return None, None


def proximo_control(fecha_atencion: datetime, meses: int | None, mes: str | None) -> tuple[datetime | None, str]:
    """Fecha sugerida del próximo control y el criterio usado para calcularla."""
    if meses:
        return fecha_atencion + relativedelta(months=int(meses)), f"Fecha atención + {int(meses)} mes(es)"
    if mes:
        y, m = map(int, mes.split("-"))
        return datetime(y, m, 1), f"Mes indicado ({m:02d}/{y}); se usa el día 1"
    return None, "Sin plazo indicado"


_NO_REQUIERE = re.compile(r"^\s*(de\s+)?alta\b|\balta\s*$|ingreso a leq|mal agendada|^\s*cancelad[oa]\s*$")


def no_requiere_control(indicacion: str) -> bool:
    """Alta, ingreso a lista quirúrgica o comprobante anulado."""
    return bool(_NO_REQUIERE.search(sin_tildes(indicacion or "").lower()))


def es_nsp(texto: str) -> bool:
    return bool(re.search(r"\bNSP\b", texto or ""))
