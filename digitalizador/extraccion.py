"""Extracción de datos del texto OCR: RUT, nombre, fechas, correo,
teléfono y tipo de documento. Pensado para documentos chilenos de admisión."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

# ---------------------------------------------------------------- RUT ---

_RE_RUT = re.compile(r"\b(\d{1,2}[.\s]?\d{3}[.\s]?\d{3})\s?[-‐–]\s?([\dkK])\b")


def digito_verificador(cuerpo: int) -> str:
    """Calcula el dígito verificador de un RUT chileno (módulo 11)."""
    suma, mult = 0, 2
    while cuerpo:
        suma += (cuerpo % 10) * mult
        cuerpo //= 10
        mult = 2 if mult == 7 else mult + 1
    dv = 11 - suma % 11
    return {11: "0", 10: "K"}.get(dv, str(dv))


def rut_valido(rut: str) -> bool:
    limpio = re.sub(r"[^\dkK]", "", rut).upper()
    if len(limpio) < 2 or not limpio[:-1].isdigit():
        return False
    return digito_verificador(int(limpio[:-1])) == limpio[-1]


def formatear_rut(rut: str) -> str:
    limpio = re.sub(r"[^\dkK]", "", rut).upper()
    cuerpo, dv = limpio[:-1], limpio[-1]
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"


def buscar_ruts(texto: str) -> list[str]:
    encontrados = []
    for m in _RE_RUT.finditer(texto):
        rut = m.group(1) + m.group(2)
        if rut_valido(rut):
            r = formatear_rut(rut)
            if r not in encontrados:
                encontrados.append(r)
    return encontrados


# ------------------------------------------------------------- Fechas ---

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
    "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}
_RE_FECHA_NUM = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})\b")
_RE_FECHA_TXT = re.compile(
    r"\b(\d{1,2})\s*(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóú]{3,10})\.?\s*(?:de(?:l)?\s+)?(\d{4})\b",
    re.IGNORECASE,
)


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def buscar_fechas(texto: str) -> list[str]:
    """Devuelve fechas en formato ISO (AAAA-MM-DD), en orden de aparición."""
    hallazgos: list[tuple[int, str]] = []
    for m in _RE_FECHA_NUM.finditer(texto):
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a < 100:
            a += 2000 if a < 50 else 1900
        if 1 <= d <= 31 and 1 <= mes <= 12 and 1900 <= a <= 2100:
            hallazgos.append((m.start(), f"{a:04d}-{mes:02d}-{d:02d}"))
    for m in _RE_FECHA_TXT.finditer(texto):
        mes = MESES.get(_sin_tildes(m.group(2)).lower())
        d, a = int(m.group(1)), int(m.group(3))
        if mes and 1 <= d <= 31 and 1900 <= a <= 2100:
            hallazgos.append((m.start(), f"{a:04d}-{mes:02d}-{d:02d}"))
    vistos, salida = set(), []
    for _, f in sorted(hallazgos):
        if f not in vistos:
            vistos.add(f)
            salida.append(f)
    return salida


# ------------------------------------------------ Correo y teléfono ---

_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_TELEFONO = re.compile(r"(?:\+?56\s?)?(?:9\s?\d{4}\s?\d{4}|[2-8]\s?\d{3,4}\s?\d{4})\b")


def buscar_correos(texto: str) -> list[str]:
    return list(dict.fromkeys(m.lower() for m in _RE_CORREO.findall(texto)))


def buscar_telefonos(texto: str) -> list[str]:
    salida = []
    for m in _RE_TELEFONO.findall(texto):
        num = re.sub(r"\s", "", m)
        if len(re.sub(r"\D", "", num)) >= 9 and num not in salida:
            salida.append(num)
    return salida


# ------------------------------------------------------------- Nombre ---

_RE_PALABRA_NOMBRE = re.compile(r"^[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñü'-]+[,.]?$")
_CONECTORES = {"de", "del", "la", "las", "los", "y"}  # "María de los Ángeles"
_RE_ETIQUETA_NOMBRE = re.compile(
    r"\b(?:nombre\s+(?:del|de\s+la)\s+(?:alumn[oa]|postulante|estudiante)|apellidos?\s+y\s+nombres?"
    r"|nombres?(?:\s+completo)?|alumn[oa](?:\s*\(a\))?|postulante|estudiante|don|do[ñn]a)\b\s*[:.]?",
    re.IGNORECASE,
)
_PALABRAS_NO_NOMBRE = {
    "rut", "run", "fecha", "curso", "colegio", "nacimiento", "certificado", "nombre", "nombres",
    "alumno", "alumna", "postulante", "estudiante", "apoderado", "domicilio", "es", "cursa",
}


def buscar_nombre(texto: str) -> str:
    """Busca un nombre después de una etiqueta ("Nombre:", "Alumno:", "don"...).
    Acepta el valor en la misma línea o en la línea siguiente (frecuente en OCR)."""
    for m in _RE_ETIQUETA_NOMBRE.finditer(texto):
        resto = texto[m.end():m.end() + 160]
        lineas = [l.strip() for l in resto.splitlines()]
        # Valor en la misma línea; si está vacía, la siguiente línea con contenido.
        candidata = lineas[0] if lineas and lineas[0] else next((l for l in lineas[1:3] if l), "")
        palabras: list[str] = []
        for p in candidata.split():
            limpia = p.strip(",.")
            if limpia.lower() in _PALABRAS_NO_NOMBRE:
                break
            if limpia.lower() in _CONECTORES and palabras:
                palabras.append(limpia.lower())
                continue
            if not _RE_PALABRA_NOMBRE.match(p):
                break
            palabras.append(limpia)
            if p.endswith(","):
                break
        while palabras and palabras[-1] in _CONECTORES:
            palabras.pop()
        if len([w for w in palabras if w not in _CONECTORES]) >= 2:
            return " ".join(w.capitalize() if w.isupper() else w for w in palabras[:7])
    return ""


# --------------------------------------------------- Tipo de documento ---

TIPOS = {
    "cedula_identidad": ["cédula de identidad", "cedula de identidad", "registro civil", "run", "identity card"],
    "certificado_nacimiento": ["certificado de nacimiento", "nacimiento", "circunscripción"],
    "certificado_notas": ["certificado anual de estudios", "concentración de notas", "calificaciones",
                          "promedio", "notas", "asignatura"],
    "certificado_alumno_regular": ["alumno regular", "alumna regular"],
    "informe_personalidad": ["informe de personalidad", "desarrollo personal", "personalidad"],
    "comprobante_domicilio": ["boleta", "domicilio", "cuenta de", "consumo"],
    "certificado_medico": ["certificado médico", "diagnóstico", "médico", "licencia"],
    "formulario_postulacion": ["postulación", "ficha de matrícula", "formulario", "apoderado"],
}


def clasificar(texto: str) -> str:
    t = texto.lower()
    puntajes = {tipo: sum(t.count(p) * (3 if " " in p else 1) for p in claves) for tipo, claves in TIPOS.items()}
    mejor = max(puntajes, key=puntajes.get)
    return mejor if puntajes[mejor] > 0 else "otro"


# ------------------------------------------------------------ Resumen ---


@dataclass
class DatosExtraidos:
    tipo_documento: str = "otro"
    nombre: str = ""
    rut: str = ""
    otros_ruts: list[str] = field(default_factory=list)
    fechas: list[str] = field(default_factory=list)
    correos: list[str] = field(default_factory=list)
    telefonos: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return asdict(self)


def extraer(texto: str) -> DatosExtraidos:
    ruts = buscar_ruts(texto)
    return DatosExtraidos(
        tipo_documento=clasificar(texto),
        nombre=buscar_nombre(texto),
        rut=ruts[0] if ruts else "",
        otros_ruts=ruts[1:],
        fechas=buscar_fechas(texto),
        correos=buscar_correos(texto),
        telefonos=buscar_telefonos(texto),
    )
