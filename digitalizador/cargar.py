"""Carga de documentos: imágenes (JPG, PNG, TIFF, HEIC si está pillow-heif) y PDF."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic", ".heif"}
EXT_PDF = {".pdf"}
EXT_SOPORTADAS = EXT_IMAGEN | EXT_PDF

try:  # Fotos de iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass


def es_soportado(ruta: Path) -> bool:
    return ruta.suffix.lower() in EXT_SOPORTADAS


def listar_documentos(entrada: Path) -> list[Path]:
    """Devuelve los archivos soportados de una carpeta (recursivo) o el archivo dado."""
    if entrada.is_file():
        return [entrada] if es_soportado(entrada) else []
    return sorted(p for p in entrada.rglob("*") if p.is_file() and es_soportado(p))


def _pdf_a_imagenes(ruta: Path, dpi: int) -> list[Image.Image]:
    # PyMuPDF no necesita programas externos (más fácil en Windows).
    try:
        import fitz  # PyMuPDF

        paginas = []
        with fitz.open(ruta) as doc:
            for pagina in doc:
                pix = pagina.get_pixmap(dpi=dpi)
                paginas.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        return paginas
    except ImportError:
        pass
    # Alternativa: pdf2image (requiere Poppler instalado).
    from pdf2image import convert_from_path

    return [p.convert("RGB") for p in convert_from_path(str(ruta), dpi=dpi)]


def cargar_paginas(ruta: Path, dpi: int = 300) -> list[Image.Image]:
    """Devuelve una lista de páginas como imágenes RGB."""
    sufijo = ruta.suffix.lower()
    if sufijo in EXT_PDF:
        return _pdf_a_imagenes(ruta, dpi)

    img = Image.open(ruta)
    paginas = []
    i = 0
    while True:  # TIFF multipágina
        try:
            img.seek(i)
        except EOFError:
            break
        # Respeta la orientación EXIF de las fotos del celular.
        paginas.append(ImageOps.exif_transpose(img.copy()).convert("RGB"))
        i += 1
    return paginas
