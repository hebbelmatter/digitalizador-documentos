"""Catálogo de especialidades.

Cada control en papel queda asociado a una especialidad, que se deduce del
"Local" impreso en el comprobante (p. ej. "HCVB-CC-NEUROC. COLUMNA COMPLEJA"
-> NEUROCIRUGÍA). Con la misma regla se clasifica el nombre de cada agenda de
Experto, de modo que un control sólo se da por atendido o agendado con citas
de su propia especialidad.

Las reglas se revisan en orden y gana la primera que calza; por eso las más
específicas van antes (NEUROCIRUGÍA antes que ONCOLOGÍA, para que
"NEUROC. ONCOLOGICA" sea neurocirugía; NEUROLOGÍA antes que UROLOGÍA).

Para agregar o corregir especialidades sin tocar el código se puede pasar un
CSV con ``--especialidades archivo.csv`` (columnas ``Especialidad;Patron``,
el patrón es una expresión regular sobre el texto en mayúsculas y sin tildes).
Esas reglas se revisan antes que las de este catálogo.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

# (nombre como aparece en Workflow, expresión regular sobre MAYÚSCULAS sin tildes)
CATALOGO: list[tuple[str, str]] = [
    ("NEUROCIRUGÍA", r"NEUROC|NEUROCIR|-NC\b"),
    ("NEUROLOGÍA", r"NEUROL"),
    ("TRAUMATOLOGÍA", r"TRAUMA"),
    ("CARDIOLOGÍA", r"CARDIOL|CARDIO\b"),
    ("CIRUGÍA CARDIOVASCULAR", r"CARDIOVASC|CIR\.? ?VASC"),
    ("OFTALMOLOGÍA", r"OFTAL"),
    ("OTORRINOLARINGOLOGÍA", r"OTORR|\bORL\b"),
    ("UROLOGÍA", r"(?<![A-Z])UROL"),
    ("GINECOLOGÍA", r"GINEC|OBSTET|\bGYO\b"),
    ("DERMATOLOGÍA", r"DERMAT"),
    ("GASTROENTEROLOGÍA", r"GASTRO"),
    ("NEFROLOGÍA", r"NEFRO"),
    ("ENDOCRINOLOGÍA", r"ENDOCR"),
    ("REUMATOLOGÍA", r"REUMA"),
    ("HEMATOLOGÍA", r"HEMATO"),
    ("ONCOLOGÍA", r"ONCOL"),
    ("BRONCOPULMONAR", r"BRONCO|PULMON|NEUMOL"),
    ("INFECTOLOGÍA", r"INFECTO"),
    ("GERIATRÍA", r"GERIAT"),
    ("PSIQUIATRÍA", r"PSIQ"),
    ("PEDIATRÍA", r"PEDIAT"),
    ("MEDICINA INTERNA", r"MED(ICINA)?\.? ?INTERNA"),
    ("CIRUGÍA PLÁSTICA", r"PLASTIC"),
    ("CIRUGÍA INFANTIL", r"CIR(UGIA)?\.? ?(INFANTIL|PEDIAT)"),
    ("CIRUGÍA", r"CIRUG|\bCIR\b"),
]


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))


def normalizar(nombre: str) -> str:
    """'Neurocirugía' -> 'NEUROCIRUGIA' (para comparar con Workflow)."""
    return re.sub(r"\s+", " ", sin_tildes(str(nombre or "")).upper()).strip()


class Catalogo:
    def __init__(self, reglas: list[tuple[str, str]] | None = None):
        self.reglas = [(n, re.compile(p)) for n, p in (reglas if reglas is not None else CATALOGO)]
        self._cache: dict[str, str] = {}

    @classmethod
    def con_archivo(cls, ruta: Path | None) -> "Catalogo":
        """Catálogo base más las reglas de un CSV (que tienen prioridad)."""
        extra: list[tuple[str, str]] = []
        if ruta:
            texto = Path(ruta).read_text(encoding="utf-8-sig")
            sep = ";" if texto.count(";") >= texto.count(",") else ","
            for fila in csv.DictReader(texto.splitlines(), delimiter=sep):
                nombre = (fila.get("Especialidad") or "").strip()
                patron = (fila.get("Patron") or fila.get("Patrón") or "").strip()
                if nombre and patron:
                    extra.append((nombre.upper(), patron))
        return cls(extra + CATALOGO)

    def de_texto(self, texto: str) -> str:
        """Especialidad de un local o nombre de agenda ('' si no se reconoce)."""
        t = normalizar(texto)
        if t not in self._cache:
            self._cache[t] = next((n for n, p in self.reglas if p.search(t)), "")
        return self._cache[t]


CATALOGO_BASE = Catalogo()


def especialidad_de(texto: str) -> str:
    return CATALOGO_BASE.de_texto(texto)
