"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__, ocr
from .procesador import Opciones, procesar, vigilar


def _opciones_comunes(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--salida", type=Path, default=Path("salida"), help="carpeta de salida (por defecto: ./salida)")
    p.add_argument("--idioma", default=ocr.IDIOMA_POR_DEFECTO, help="idiomas de Tesseract, p. ej. spa o spa+eng")
    p.add_argument("--dpi", type=int, default=300, help="resolución al leer PDF (por defecto 300)")
    p.add_argument("--postulante", help="guardar todo en la carpeta de este postulante")
    p.add_argument("--sin-agrupar", action="store_true", help="no crear carpetas por RUT")
    p.add_argument("--sin-limpieza", action="store_true", help="no limpiar la imagen (para escaneos ya buenos)")
    p.add_argument("--sin-recorte", action="store_true", help="no buscar el borde de la hoja en fotos")
    p.add_argument("--copiar-original", action="store_true", help="guardar una copia del archivo original")
    p.add_argument("--forzar", action="store_true", help="reprocesar aunque ya se haya procesado")
    p.add_argument("--tesseract", help="ruta a tesseract(.exe) si no está en el PATH")


def _armar_opciones(a: argparse.Namespace) -> Opciones:
    return Opciones(
        idioma=a.idioma,
        dpi=a.dpi,
        limpiar=not a.sin_limpieza,
        recortar=not a.sin_recorte,
        agrupar_por_rut=not a.sin_agrupar,
        postulante=a.postulante,
        copiar_original=a.copiar_original,
        forzar=a.forzar,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="digitalizar",
        description="Digitaliza documentos en local: limpieza, OCR en español, PDF buscable y extracción de datos.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("procesar", help="procesar un archivo o una carpeta")
    p.add_argument("entrada", type=Path, help="archivo o carpeta con imágenes/PDF")
    _opciones_comunes(p)

    v = sub.add_parser("vigilar", help="procesar automáticamente lo que llegue a una carpeta")
    v.add_argument("carpeta", type=Path)
    v.add_argument("--intervalo", type=float, default=3.0, help="segundos entre revisiones")
    _opciones_comunes(v)

    w = sub.add_parser("web", help="abrir la interfaz web local")
    w.add_argument("-o", "--salida", type=Path, default=Path("salida"))
    w.add_argument("--puerto", type=int, default=8765)
    w.add_argument("--idioma", default=ocr.IDIOMA_POR_DEFECTO)
    w.add_argument("--tesseract")
    w.add_argument("--no-abrir", action="store_true", help="no abrir el navegador")

    a = parser.parse_args(argv)
    ocr.configurar_tesseract(a.tesseract)

    if a.comando == "procesar":
        if not a.entrada.exists():
            parser.error(f"No existe: {a.entrada}")
        filas = procesar(a.entrada, a.salida, _armar_opciones(a))
        print(f"\nListo: {len(filas)} documento(s). Resumen en {a.salida / 'resumen.csv'}")
    elif a.comando == "vigilar":
        a.carpeta.mkdir(parents=True, exist_ok=True)
        vigilar(a.carpeta, a.salida, _armar_opciones(a), intervalo=a.intervalo)
    elif a.comando == "web":
        from .web import iniciar

        iniciar(a.salida, puerto=a.puerto, idioma=a.idioma, abrir=not a.no_abrir)
    return 0
