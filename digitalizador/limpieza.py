"""Limpieza de imagen: recorte del documento en fotos, corrección de
perspectiva, enderezado y mejora de contraste."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def _pil_a_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _cv_a_pil(arr: np.ndarray) -> Image.Image:
    if arr.ndim == 2:
        return Image.fromarray(arr)
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def _ordenar_puntos(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # sup-izq
    rect[2] = pts[np.argmax(s)]  # inf-der
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]  # sup-der
    rect[3] = pts[np.argmax(d)]  # inf-izq
    return rect


def recortar_documento(img: np.ndarray, area_minima: float = 0.25) -> np.ndarray:
    """Busca el contorno de una hoja en una foto y corrige la perspectiva.
    Si no encuentra una hoja clara, devuelve la imagen sin cambios."""
    alto, ancho = img.shape[:2]
    escala = 1000.0 / max(alto, ancho)
    peq = cv2.resize(img, None, fx=escala, fy=escala) if escala < 1 else img.copy()
    if escala >= 1:
        escala = 1.0

    gris = cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (5, 5), 0)
    bordes = cv2.Canny(gris, 50, 150)
    bordes = cv2.dilate(bordes, np.ones((3, 3), np.uint8), iterations=2)

    contornos, _ = cv2.findContours(bordes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total = peq.shape[0] * peq.shape[1]
    for c in sorted(contornos, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < area_minima * area_total:
            break
        aprox = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(aprox) != 4:
            continue
        # Si la hoja ya ocupa casi toda la imagen (escaneo), no hace falta.
        if cv2.contourArea(aprox) > 0.97 * area_total:
            return img
        rect = _ordenar_puntos(aprox.reshape(4, 2).astype("float32") / escala)
        (tl, tr, br, bl) = rect
        w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
        destino = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
        m = cv2.getPerspectiveTransform(rect, destino)
        return cv2.warpPerspective(img, m, (w, h))
    return img


def angulo_inclinacion(gris: np.ndarray) -> float:
    """Estima la inclinación del texto (grados) a partir de las líneas de texto."""
    binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    # Une letras en líneas para que el ángulo sea estable.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, gris.shape[1] // 50), 3))
    lineas = cv2.dilate(binaria, kernel, iterations=1)
    contornos, _ = cv2.findContours(lineas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    angulos, pesos = [], []
    for c in contornos:
        (_, _), (w, h), ang = cv2.minAreaRect(c)
        if w < h:
            w, h = h, w
            ang = ang - 90
        if w < gris.shape[1] * 0.1 or h == 0 or w / h < 3:
            continue
        if ang < -45:
            ang += 90
        elif ang > 45:
            ang -= 90
        angulos.append(ang)
        pesos.append(w)
    if not angulos:
        return 0.0
    return float(np.average(angulos, weights=pesos))


def enderezar(img: np.ndarray, gris: np.ndarray) -> np.ndarray:
    ang = angulo_inclinacion(gris)
    if abs(ang) < 0.3 or abs(ang) > 15:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    borde = 255 if img.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=borde)


def mejorar(gris: np.ndarray) -> np.ndarray:
    """Normaliza la iluminación (sombras de fotos) y aumenta el contraste."""
    fondo = cv2.morphologyEx(gris, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    normal = cv2.divide(gris, fondo, scale=255)
    return cv2.fastNlMeansDenoising(normal, h=10)


def limpiar_pagina(img: Image.Image, recortar: bool = True) -> Image.Image:
    """Devuelve la página limpia en escala de grises, lista para OCR y PDF."""
    arr = _pil_a_cv(img)
    if recortar:
        arr = recortar_documento(arr)
    gris = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    gris = enderezar(gris, gris)
    # Asegura resolución suficiente para el OCR.
    if max(gris.shape) < 1600:
        f = 1600 / max(gris.shape)
        gris = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    return _cv_a_pil(mejorar(gris))
