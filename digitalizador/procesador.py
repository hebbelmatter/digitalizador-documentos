"""Flujo completo: cargar → limpiar → OCR → PDF buscable → extracción → archivos de salida."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import cargar, extraccion, limpieza, ocr

COLUMNAS_CSV = [
    "procesado", "archivo_original", "carpeta", "pdf", "paginas", "confianza_ocr",
    "tipo_documento", "nombre", "rut", "otros_ruts", "fechas", "correos", "telefonos",
]
REGISTRO = ".procesados.json"


@dataclass
class Opciones:
    idioma: str = ocr.IDIOMA_POR_DEFECTO
    dpi: int = 300
    limpiar: bool = True
    recortar: bool = True
    agrupar_por_rut: bool = True
    postulante: str | None = None
    copiar_original: bool = False
    forzar: bool = False


def _hash(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _nombre_seguro(texto: str) -> str:
    texto = re.sub(r"[^\w.\- ]", "", texto, flags=re.UNICODE).strip().replace(" ", "_")
    return texto[:80] or "documento"


def _cargar_registro(salida: Path) -> dict:
    archivo = salida / REGISTRO
    if archivo.exists():
        try:
            return json.loads(archivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _guardar_registro(salida: Path, registro: dict) -> None:
    (salida / REGISTRO).write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")


def _agregar_csv(salida: Path, fila: dict) -> None:
    archivo = salida / "resumen.csv"
    nuevo = not archivo.exists()
    # utf-8-sig para que Excel muestre bien las tildes.
    with open(archivo, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_CSV, delimiter=";")
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def procesar_archivo(
    ruta: Path,
    salida: Path,
    opciones: Opciones,
    progreso: Callable[[str], None] = lambda _m: None,
) -> dict | None:
    """Procesa un documento. Devuelve la fila de resumen, o None si ya estaba procesado."""
    salida.mkdir(parents=True, exist_ok=True)
    registro = _cargar_registro(salida)
    huella = _hash(ruta)
    if huella in registro and not opciones.forzar:
        progreso(f"Ya procesado, se omite: {ruta.name}")
        return None

    progreso(f"Leyendo {ruta.name}")
    paginas = cargar.cargar_paginas(ruta, dpi=opciones.dpi)

    textos, pdfs, confs = [], [], []
    for i, pagina in enumerate(paginas, 1):
        progreso(f"  página {i}/{len(paginas)}: limpieza y OCR")
        if opciones.limpiar:
            pagina = limpieza.limpiar_pagina(pagina, recortar=opciones.recortar)
        pagina = ocr.corregir_orientacion(pagina)
        texto, pdf, conf = ocr.ocr_pagina(pagina, idioma=opciones.idioma)
        textos.append(texto)
        pdfs.append(pdf)
        confs.append(conf)

    texto_total = "\n\n".join(f"--- Página {i} ---\n{t.strip()}" for i, t in enumerate(textos, 1))
    datos = extraccion.extraer(texto_total)

    # Carpeta de destino: postulante indicado, RUT detectado o "sin_identificar".
    if opciones.postulante:
        carpeta = _nombre_seguro(opciones.postulante)
    elif opciones.agrupar_por_rut:
        carpeta = datos.rut.replace(".", "") if datos.rut else "sin_identificar"
    else:
        carpeta = ""
    destino = salida / carpeta if carpeta else salida
    destino.mkdir(parents=True, exist_ok=True)

    base = f"{datos.tipo_documento}_{_nombre_seguro(ruta.stem)}"
    pdf_destino = destino / f"{base}.pdf"
    n = 2
    while pdf_destino.exists() and not opciones.forzar:
        pdf_destino = destino / f"{base}_{n}.pdf"
        n += 1
    base = pdf_destino.stem

    ocr.unir_pdfs(pdfs, pdf_destino, titulo=f"{datos.tipo_documento} {datos.nombre}".strip())
    (destino / f"{base}.txt").write_text(texto_total, encoding="utf-8")
    meta = {
        "archivo_original": str(ruta),
        "sha256": huella,
        "procesado": datetime.now().isoformat(timespec="seconds"),
        "paginas": len(paginas),
        "confianza_ocr": round(sum(confs) / len(confs), 1) if confs else 0,
        "confianza_por_pagina": [round(c, 1) for c in confs],
        **datos.como_dict(),
    }
    (destino / f"{base}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if opciones.copiar_original:
        originales = destino / "originales"
        originales.mkdir(exist_ok=True)
        shutil.copy2(ruta, originales / ruta.name)

    fila = {
        "procesado": meta["procesado"],
        "archivo_original": ruta.name,
        "carpeta": carpeta,
        "pdf": str(pdf_destino.relative_to(salida)),
        "paginas": meta["paginas"],
        "confianza_ocr": meta["confianza_ocr"],
        "tipo_documento": datos.tipo_documento,
        "nombre": datos.nombre,
        "rut": datos.rut,
        "otros_ruts": ", ".join(datos.otros_ruts),
        "fechas": ", ".join(datos.fechas),
        "correos": ", ".join(datos.correos),
        "telefonos": ", ".join(datos.telefonos),
    }
    _agregar_csv(salida, fila)
    registro[huella] = {"archivo": ruta.name, "pdf": fila["pdf"]}
    _guardar_registro(salida, registro)
    aviso = "  ⚠ confianza baja, revisar" if meta["confianza_ocr"] < 60 else ""
    progreso(f"  → {fila['pdf']} ({datos.tipo_documento}, RUT {datos.rut or '—'}){aviso}")
    return fila


def procesar(
    entrada: Path, salida: Path, opciones: Opciones, progreso: Callable[[str], None] = print
) -> list[dict]:
    archivos = cargar.listar_documentos(entrada)
    if not archivos:
        progreso(f"No se encontraron documentos soportados en {entrada}")
        return []
    filas = []
    for ruta in archivos:
        if salida.resolve() in ruta.resolve().parents:
            continue  # no reprocesar la carpeta de salida
        try:
            fila = procesar_archivo(ruta, salida, opciones, progreso)
            if fila:
                filas.append(fila)
        except Exception as e:  # un archivo malo no detiene el lote
            progreso(f"  ✗ Error con {ruta.name}: {e}")
    return filas


def vigilar(
    carpeta: Path, salida: Path, opciones: Opciones, intervalo: float = 3.0, progreso: Callable[[str], None] = print
) -> None:
    """Procesa automáticamente lo que llegue a una carpeta (p. ej. la carpeta del escáner)."""
    progreso(f"Vigilando {carpeta} (Ctrl+C para detener)…")
    tamanos: dict[Path, int] = {}
    try:
        while True:
            for ruta in cargar.listar_documentos(carpeta):
                if salida.resolve() in ruta.resolve().parents:
                    continue
                tam = ruta.stat().st_size
                # Espera a que el archivo termine de copiarse.
                if tamanos.get(ruta) != tam:
                    tamanos[ruta] = tam
                    continue
                try:
                    procesar_archivo(ruta, salida, opciones, progreso)
                except Exception as e:
                    progreso(f"  ✗ Error con {ruta.name}: {e}")
            time.sleep(intervalo)
    except KeyboardInterrupt:
        progreso("Detenido.")
