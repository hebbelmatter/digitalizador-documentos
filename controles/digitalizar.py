"""Paso 1: PDF/imágenes de comprobantes -> revision.xlsx.

Por cada página: corrige la orientación, hace OCR de los datos impresos,
guarda una imagen de la mitad superior (donde está la indicación manuscrita)
y agrega una fila a la planilla de revisión. Si la planilla ya existe, las
columnas que completó una persona se conservan.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from PIL import Image, ImageOps

from digitalizador import cargar, ocr

from .comprobante import contar_comprobantes, leer_comprobante
from .especialidades import Catalogo

# Columnas de la planilla de revisión. Las marcadas como manuales se
# conservan al volver a correr "digitalizar".
COL_ID = "ID"
COLUMNAS_AUTO = ["Archivo", "Página", "N° en página", "RUN", "RUN válido", "Nombre",
                 "Fecha citación", "Hora", "Local", "Especialidad", "Profesional", "Teleconsulta"]
COLUMNAS_MANUALES = ["Indicación manuscrita", "Plazo (meses)", "Mes indicado (AAAA-MM)",
                     "Fecha citación corregida", "RUN corregido", "Nombre corregido", "Especialidad corregida",
                     "Anotaciones de contacto", "Excluir (S/N)", "Revisado (S/N)"]
COLUMNAS = [COL_ID] + COLUMNAS_AUTO + COLUMNAS_MANUALES + ["Imagen"]

AMARILLO = PatternFill("solid", fgColor="FFF2CC")


@dataclass
class OpcionesDigitalizar:
    dpi: int = 150
    idioma: str = "eng"  # los comprobantes son mayúsculas sin tildes; eng lee mejor los números
    transcribir_con_claude: bool = False
    modelo: str = "claude-sonnet-5-5"
    especialidades: Path | None = None  # CSV con reglas extra (ver especialidades.py)
    reprocesar: bool = False  # volver a leer PDF que ya están en revision.xlsx


def _orientar(img: Image.Image, idioma: str) -> tuple[Image.Image, str]:
    """Devuelve la imagen derecha y su texto OCR. Prueba 0/90/180/270° si hace falta."""
    gris = ImageOps.grayscale(img)
    texto = pytesseract.image_to_string(gris, lang=idioma, config="--psm 4")
    if re.search(r"COMPROBANTE|Citaci|RUN", texto, re.I):
        return gris, texto
    mejor = (0, gris, texto)
    for ang in (90, 270, 180):
        g = gris.rotate(ang, expand=True)
        t = pytesseract.image_to_string(g, lang=idioma, config="--psm 4")
        puntos = len(re.findall(r"COMPROBANTE|Citaci|RUN|Paciente", t, re.I))
        if puntos > mejor[0]:
            mejor = (puntos, g, t)
    return mejor[1], mejor[2]


def _texto_zona_datos(img: Image.Image, idioma: str) -> str:
    """Segundo OCR sólo de la zona de datos (mejora RUN y nombre)."""
    w, h = img.size
    recorte = img.crop((0, int(h * 0.15), int(w * 0.80), int(h * 0.48)))
    return pytesseract.image_to_string(recorte, lang=idioma, config="--psm 6")


def _imagen_revision(img: Image.Image, destino: Path) -> None:
    w, h = img.size
    mitad = img.crop((0, 0, w, int(h * 0.5)))
    mitad.thumbnail((1400, 1400))
    mitad.save(destino, "JPEG", quality=70)


_PROMPT = """Esta es la mitad superior de un comprobante de citación de un hospital chileno.
Sobre el comprobante, el médico o el personal de admisión escribió a mano.
Responde SOLO con un JSON con estas claves (cadena vacía si no hay):
"indicacion": lo escrito junto a "Próximo control" o indicaciones del médico (p. ej. "Control 3 meses con resonancia"),
"anotaciones": otras anotaciones manuscritas o timbres (contactos telefónicos, NSP, "avisado", fechas, folios),
"fecha_citacion_corregida": si la fecha de citación impresa fue tachada y corregida a mano, la fecha nueva en dd/mm/aaaa,
"run_corregido": si el RUN fue corregido a mano, el RUN nuevo.
Si una lectura es dudosa, agrega "(?)" a esa parte."""


def transcribir_con_claude(ruta_imagen: Path, modelo: str) -> dict:
    """Lee el manuscrito con la API de Claude. Requiere ANTHROPIC_API_KEY.
    OJO: envía la imagen (con datos del paciente) fuera del computador."""
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise RuntimeError("Falta la variable de entorno ANTHROPIC_API_KEY")
    datos = base64.b64encode(ruta_imagen.read_bytes()).decode()
    cuerpo = {
        "model": modelo,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": datos}},
            {"type": "text", "text": _PROMPT},
        ]}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(cuerpo).encode(),
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        respuesta = json.loads(r.read())
    texto = "".join(b.get("text", "") for b in respuesta.get("content", []))
    m = re.search(r"\{.*\}", texto, re.S)
    return json.loads(m.group(0)) if m else {}


def _leer_revision_existente(ruta: Path) -> dict[str, dict]:
    nuevo = ruta.with_name(ruta.stem + "_nuevo.xlsx")  # quedó de un guardado con Excel abierto
    if nuevo.exists() and (not ruta.exists() or nuevo.stat().st_mtime > ruta.stat().st_mtime):
        ruta = nuevo
    if not ruta.exists():
        return {}
    wb = load_workbook(ruta)
    ws = wb["Revisión"] if "Revisión" in wb.sheetnames else wb.worksheets[0]
    cab = [c.value for c in ws[1]]
    filas = {}
    for fila in ws.iter_rows(min_row=2, values_only=True):
        d = dict(zip(cab, fila))
        if d.get(COL_ID):
            filas[d[COL_ID]] = d
    return filas


def digitalizar(entrada: Path, salida: Path, opciones: OpcionesDigitalizar | None = None, avisar=print) -> Path:
    """Procesa los PDF/imágenes de ``entrada`` y actualiza ``salida/revision.xlsx``.

    * Los comprobantes que ya estaban en la planilla se conservan, aunque su
      PDF no esté en ``entrada`` (así se pueden agregar carpetas por partes).
    * Los PDF ya procesados se omiten, salvo con ``op.reprocesar``.
    * La planilla se guarda después de cada PDF: si el proceso se corta, al
      volver a correrlo sigue desde donde quedó.
    """
    op = opciones or OpcionesDigitalizar()
    ocr.configurar_tesseract()
    salida.mkdir(parents=True, exist_ok=True)
    carpeta_img = salida / "imagenes"
    carpeta_img.mkdir(exist_ok=True)
    ruta_rev = salida / "revision.xlsx"
    previas = _leer_revision_existente(ruta_rev)
    # Filas por archivo, en el orden en que se fueron agregando.
    por_archivo: dict[str, list[dict]] = {}
    for f in previas.values():
        por_archivo.setdefault(str(f.get("Archivo") or ""), []).append(f)

    catalogo = Catalogo.con_archivo(op.especialidades)
    documentos = list(cargar.listar_documentos(entrada))
    pendientes = [d for d in documentos if op.reprocesar or d.name not in por_archivo]
    omitidos = len(documentos) - len(pendientes)
    if omitidos:
        avisar(f"{omitidos} archivo(s) ya estaban en revision.xlsx y se omiten "
               "(usa --reprocesar para leerlos de nuevo).")
    if not pendientes:
        avisar("No hay archivos nuevos que procesar.")
    for i, doc in enumerate(pendientes, start=1):
        avisar(f"[{i}/{len(pendientes)}] {doc.name}: cargando…")
        paginas = cargar.cargar_paginas(doc, dpi=op.dpi)
        avisar(f"[{i}/{len(pendientes)}] {doc.name}: {len(paginas)} página(s)")
        filas_doc = []
        for n_pag, img in enumerate(paginas, start=1):
            if n_pag % 10 == 0:
                avisar(f"    página {n_pag} de {len(paginas)}")
            filas_doc += _filas_de_pagina(doc, n_pag, img, op, catalogo, carpeta_img, previas, avisar)
        del paginas
        por_archivo[doc.name] = filas_doc
        _guardar(ruta_rev, por_archivo, avisar)
    if not pendientes and not ruta_rev.exists():
        _guardar(ruta_rev, por_archivo, avisar)
    total = sum(len(v) for v in por_archivo.values())
    avisar(f"\n{total} comprobantes en {ruta_rev}")
    return ruta_rev


def _filas_de_pagina(doc: Path, n_pag: int, img: Image.Image, op: OpcionesDigitalizar, catalogo: Catalogo,
                     carpeta_img: Path, previas: dict[str, dict], avisar) -> list[dict]:
    derecha, texto = _orientar(img, op.idioma)
    zona = _texto_zona_datos(derecha, op.idioma)
    c = leer_comprobante(texto, zona)
    filas = []
    for k in range(1, contar_comprobantes(texto) + 1):
        fid = f"{doc.stem}|{n_pag}|{k}"
        nombre_img = re.sub(r"[^\w\-]+", "_", f"{doc.stem}_p{n_pag:03d}") + ".jpg"
        if k == 1:
            _imagen_revision(derecha, carpeta_img / nombre_img)
        fila = {COL_ID: fid, "Archivo": doc.name, "Página": n_pag, "N° en página": k,
                "Imagen": f"imagenes/{nombre_img}"}
        if k == 1:  # el OCR sólo es fiable para el primer comprobante de la hoja
            fila.update({"RUN": c.run, "RUN válido": "SÍ" if c.run_valido else "NO", "Nombre": c.nombre,
                         "Fecha citación": c.fecha_citacion, "Hora": c.hora, "Local": c.local,
                         "Especialidad": catalogo.de_texto(c.local) or None,
                         "Profesional": c.profesional, "Teleconsulta": "SÍ" if c.teleconsulta else ""})
        previa = previas.get(fid, {})
        for col in COLUMNAS_MANUALES:
            fila[col] = previa.get(col)
        if op.transcribir_con_claude and k == 1 and not fila.get("Indicación manuscrita"):
            try:
                t = transcribir_con_claude(carpeta_img / nombre_img, op.modelo)
                fila["Indicación manuscrita"] = t.get("indicacion") or None
                fila["Anotaciones de contacto"] = t.get("anotaciones") or None
                fila["Fecha citación corregida"] = t.get("fecha_citacion_corregida") or None
                fila["RUN corregido"] = t.get("run_corregido") or None
            except Exception as e:  # noqa: BLE001 - se informa y se sigue
                avisar(f"  ⚠ no se pudo transcribir {fid}: {e}")
        filas.append(fila)
    return filas


def _guardar(ruta: Path, por_archivo: dict[str, list[dict]], avisar) -> None:
    """Guarda la planilla sin dejarla a medio escribir. Si está abierta en
    Excel (Windows la bloquea), avisa y lo vuelve a intentar con el próximo PDF."""
    filas = [f for fs in por_archivo.values() for f in fs]
    tmp = ruta.with_name(ruta.stem + ".tmp.xlsx")
    _escribir_revision(tmp, filas)
    try:
        os.replace(tmp, ruta)
    except PermissionError:
        respaldo = ruta.with_name(ruta.stem + "_nuevo.xlsx")
        os.replace(tmp, respaldo)
        avisar(f"  ⚠ {ruta.name} está abierto en Excel; se guardó en {respaldo.name}. "
               f"Ciérralo y el próximo guardado lo actualizará.")


def _escribir_revision(ruta: Path, filas: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Revisión"
    ws.append(COLUMNAS)
    for f in filas:
        ws.append([f.get(c) for c in COLUMNAS])
    for c in ws[1]:
        c.font = Font(bold=True)
        if c.value in COLUMNAS_MANUALES:
            c.fill = AMARILLO
    col_img = COLUMNAS.index("Imagen") + 1
    for fila in ws.iter_rows(min_row=2):
        celda = fila[col_img - 1]
        if celda.value:
            celda.hyperlink = celda.value
            celda.style = "Hyperlink"
    anchos = {"ID": 28, "Archivo": 28, "Nombre": 34, "Local": 34, "Profesional": 32,
              "Indicación manuscrita": 45, "Anotaciones de contacto": 50, "Imagen": 30}
    for i, col in enumerate(COLUMNAS, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = anchos.get(col, 14)
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    leyenda = wb.create_sheet("Instrucciones")
    for linea in [
        "Completa las columnas amarillas mirando la imagen de cada comprobante (columna Imagen).",
        "Indicación manuscrita: lo que escribió el médico, p. ej. 'Control 3 meses con resonancia'.",
        "Plazo (meses) / Mes indicado: déjalos vacíos si la indicación ya dice '3 meses', '1 año' o 'abril 2026'; se calculan solos.",
        "Fecha citación corregida / RUN corregido / Nombre corregido: sólo si el impreso está mal o tachado.",
        "Especialidad corregida: sólo si la columna Especialidad (deducida del Local) está vacía o mal.",
        "Excluir (S/N): S para hojas sin datos de paciente o copias que no deben contarse.",
        "Agrega 'NSP' en Anotaciones si el paciente no se presentó.",
        "Si vuelves a correr 'digitalizar', lo que escribiste en estas columnas se conserva.",
    ]:
        leyenda.append([linea])
    leyenda.column_dimensions["A"].width = 120
    wb.save(ruta)
