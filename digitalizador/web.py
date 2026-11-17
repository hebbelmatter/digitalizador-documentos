"""Interfaz web local (solo en tu computador: http://127.0.0.1:8765).
Arrastra archivos, se procesan y quedan listados con sus datos."""

from __future__ import annotations

import csv
import tempfile
import threading
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from .cargar import es_soportado
from .procesador import Opciones, procesar_archivo

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Digitalizador de documentos</title>
<style>
 :root{--bg:#f6f5f1;--card:#fff;--ink:#1d1d1b;--muted:#6b6a65;--line:#e4e2db;--acc:#1f5f8b;--ok:#2e7d4f;--warn:#b26a00}
 *{box-sizing:border-box} body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
 main{max-width:1100px;margin:0 auto;padding:32px 20px}
 h1{font-size:22px;margin:0 0 4px} p.sub{color:var(--muted);margin:0 0 20px}
 .zona{border:2px dashed var(--line);background:var(--card);border-radius:12px;padding:36px;text-align:center;cursor:pointer;transition:.15s}
 .zona.activa{border-color:var(--acc);background:#eef4f9}
 .fila{display:flex;gap:12px;align-items:center;margin:14px 0;flex-wrap:wrap}
 input[type=text]{padding:8px 10px;border:1px solid var(--line);border-radius:8px;min-width:260px;font:inherit}
 label{color:var(--muted);font-size:14px}
 table{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;margin-top:18px}
 th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:14px;vertical-align:top}
 th{background:#efede7;font-weight:600} td.n{font-variant-numeric:tabular-nums}
 .bajo{color:var(--warn);font-weight:600} .ok{color:var(--ok)}
 #log{font:12px ui-monospace,Menlo,monospace;color:var(--muted);white-space:pre-wrap;margin-top:10px}
 a{color:var(--acc)} .acciones{display:flex;gap:16px;margin-top:10px}
</style></head><body><main>
<h1>Digitalizador de documentos</h1>
<p class="sub">Todo se procesa en este computador. Imágenes (JPG, PNG, HEIC, TIFF) o PDF.</p>
<div class="fila"><label for="post">Postulante (opcional):</label>
<input id="post" type="text" placeholder="Si lo dejas vacío, se agrupa por RUT detectado"></div>
<div class="zona" id="zona">Arrastra aquí los documentos o <u>haz clic para elegir</u>
<input id="archivos" type="file" multiple accept="image/*,.pdf,.heic" hidden></div>
<div id="log"></div>
<div class="acciones"><a href="/resumen.csv">Descargar resumen.csv</a></div>
<table><thead><tr><th>Documento</th><th>Tipo</th><th>Nombre</th><th>RUT</th><th>Fechas</th>
<th>Pág.</th><th>Conf. OCR</th><th>PDF</th></tr></thead><tbody id="tabla"></tbody></table>
</main><script>
const zona=document.getElementById('zona'),inp=document.getElementById('archivos'),log=document.getElementById('log');
zona.onclick=()=>inp.click();
['dragenter','dragover'].forEach(e=>zona.addEventListener(e,ev=>{ev.preventDefault();zona.classList.add('activa')}));
['dragleave','drop'].forEach(e=>zona.addEventListener(e,ev=>{ev.preventDefault();zona.classList.remove('activa')}));
zona.addEventListener('drop',ev=>subir(ev.dataTransfer.files));
inp.onchange=()=>subir(inp.files);
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function subir(lista){
  for(const f of lista){
    log.textContent+=`Procesando ${f.name}…\\n`;
    const fd=new FormData();fd.append('archivo',f);fd.append('postulante',document.getElementById('post').value);
    try{const r=await fetch('/procesar',{method:'POST',body:fd});const j=await r.json();
      log.textContent+=(j.error?`✗ ${j.error}`:`✓ ${f.name}`)+'\\n';}catch(e){log.textContent+=`✗ ${e}\\n`}
    cargar();
  }
}
async function cargar(){
  const filas=await (await fetch('/documentos')).json();
  document.getElementById('tabla').innerHTML=filas.reverse().map(f=>`<tr>
   <td>${esc(f.archivo_original)}</td><td>${esc(f.tipo_documento)}</td><td>${esc(f.nombre)}</td>
   <td>${esc(f.rut)}</td><td>${esc(f.fechas)}</td><td class="n">${esc(f.paginas)}</td>
   <td class="n ${parseFloat(f.confianza_ocr)<60?'bajo':'ok'}">${esc(f.confianza_ocr)}</td>
   <td><a href="/archivo/${encodeURI(f.pdf)}" target="_blank">abrir</a></td></tr>`).join('');
}
cargar();
</script></body></html>"""


def crear_app(salida: Path, idioma: str = "spa") -> Flask:
    salida = salida.resolve()
    salida.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
    candado = threading.Lock()  # un documento a la vez

    @app.get("/")
    def inicio():
        return PAGINA

    @app.post("/procesar")
    def procesar():
        archivo = request.files.get("archivo")
        if not archivo or not archivo.filename:
            return jsonify(error="No se recibió archivo"), 400
        nombre = secure_filename(archivo.filename) or "documento"
        if not es_soportado(Path(nombre)):
            return jsonify(error=f"Formato no soportado: {nombre}"), 400
        postulante = (request.form.get("postulante") or "").strip() or None
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / nombre
            archivo.save(ruta)
            with candado:
                try:
                    fila = procesar_archivo(ruta, salida, Opciones(idioma=idioma, postulante=postulante))
                except Exception as e:
                    return jsonify(error=str(e)), 500
        return jsonify(fila or {"omitido": True})

    @app.get("/documentos")
    def documentos():
        archivo = salida / "resumen.csv"
        if not archivo.exists():
            return jsonify([])
        with open(archivo, encoding="utf-8-sig") as f:
            return jsonify(list(csv.DictReader(f, delimiter=";")))

    @app.get("/resumen.csv")
    def resumen():
        if not (salida / "resumen.csv").exists():
            abort(404)
        return send_from_directory(salida, "resumen.csv", as_attachment=True)

    @app.get("/archivo/<path:ruta>")
    def archivo(ruta):
        return send_from_directory(salida, ruta)  # send_from_directory impide salir de la carpeta

    return app


def iniciar(salida: Path, puerto: int = 8765, idioma: str = "spa", abrir: bool = True) -> None:
    app = crear_app(salida, idioma)
    url = f"http://127.0.0.1:{puerto}"
    print(f"Digitalizador abierto en {url}  (salida: {salida.resolve()})  — Ctrl+C para cerrar")
    if abrir:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=puerto, debug=False)
