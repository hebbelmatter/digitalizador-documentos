"""OCR con Tesseract y generación de PDF buscable."""

from __future__ import annotations

import io
import os
import shutil
from pathlib import Path

import pytesseract
from PIL import Image
from pypdf import PdfReader, PdfWriter

# "spa+eng": el modelo inglés reconoce mejor símbolos como "@" sin perder tildes.
IDIOMA_POR_DEFECTO = "spa+eng"


def configurar_tesseract(ruta: str | None = None) -> None:
    """Ubica tesseract.exe en Windows si no está en el PATH."""
    ruta = ruta or os.environ.get("TESSERACT_CMD")
    if ruta:
        pytesseract.pytesseract.tesseract_cmd = ruta
        return
    if shutil.which("tesseract"):
        return
    for candidato in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ):
        if Path(candidato).exists():
            pytesseract.pytesseract.tesseract_cmd = candidato
            return


def corregir_orientacion(img: Image.Image) -> Image.Image:
    """Gira páginas que vienen de lado o al revés (90/180/270)."""
    try:
        osd = pytesseract.image_to_osd(img, config="--psm 0", output_type=pytesseract.Output.DICT)
        rot = int(osd.get("rotate", 0))
        if rot and float(osd.get("orientation_conf", 0)) > 2:
            return img.rotate(-rot, expand=True, fillcolor=255)
    except pytesseract.TesseractError:
        pass  # poca información en la página; se deja igual
    return img


def ocr_pagina(img: Image.Image, idioma: str = IDIOMA_POR_DEFECTO) -> tuple[str, bytes, float]:
    """Devuelve (texto, pdf_de_una_página_buscable, confianza_media)."""
    texto = pytesseract.image_to_string(img, lang=idioma, config="--psm 3")
    pdf = pytesseract.image_to_pdf_or_hocr(img, lang=idioma, extension="pdf")
    datos = pytesseract.image_to_data(img, lang=idioma, output_type=pytesseract.Output.DICT)
    confs = [float(c) for c, t in zip(datos["conf"], datos["text"]) if t.strip() and float(c) >= 0]
    conf = sum(confs) / len(confs) if confs else 0.0
    return texto, pdf, conf


def unir_pdfs(paginas_pdf: list[bytes], destino: Path, titulo: str = "") -> None:
    escritor = PdfWriter()
    for datos in paginas_pdf:
        for pagina in PdfReader(io.BytesIO(datos)).pages:
            escritor.add_page(pagina)
    if titulo:
        escritor.add_metadata({"/Title": titulo, "/Producer": "digitalizador-documentos"})
    escritor.compress_identical_objects()
    with open(destino, "wb") as f:
        escritor.write(f)
