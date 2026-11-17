# Digitalizador de documentos

Programa que corre **en tu computador**, sin subir nada a internet, y convierte escaneos, fotos del celular o PDF en:

- un **PDF buscable**, con la imagen limpia y el texto seleccionable;
- el **texto completo** (`.txt`) y los **datos extraídos** (`.json`);
- una fila nueva en **`resumen.csv`**, que se abre directo en Excel.

Pensado para los documentos de **admisión**: cédula, certificado de nacimiento, certificado de notas, alumno regular, informe de personalidad, etc.

## Qué hace con cada documento

1. **Limpia la imagen**: en las fotos detecta el borde de la hoja y corrige la perspectiva. Además endereza el texto inclinado, quita sombras y ruido, y gira las páginas que vienen de lado.
2. **Hace OCR** en español con Tesseract.
3. **Extrae datos**:
   - RUT/RUN, validando el dígito verificador
   - nombre
   - fechas, en formato AAAA-MM-DD
   - correo y teléfono
   - tipo de documento
4. **Ordena** los archivos en una carpeta por postulante: usa el RUT detectado o el nombre que le indiques.
5. **No repite trabajo**: si vuelves a pasar el mismo archivo, se omite.

```
salida/
├── resumen.csv
├── 21345678-4/
│   ├── certificado_notas_foto_celular.pdf   ← PDF buscable
│   ├── certificado_notas_foto_celular.txt
│   └── certificado_notas_foto_celular.json
└── sin_identificar/                         ← documentos sin RUT legible
```

## Instalación

### 1. Instalar Tesseract (el motor de OCR)

- **Windows**: descarga el instalador desde <https://github.com/UB-Mannheim/tesseract/wiki>. Al instalar, marca **Spanish** en *Additional language data*.
- **macOS**: `brew install tesseract tesseract-lang`
- **Ubuntu/Debian**: `sudo apt install tesseract-ocr tesseract-ocr-spa`

### 2. Instalar Python 3.10 o superior

Lo descargas desde <https://www.python.org/downloads/>. En Windows, marca *Add Python to PATH*.

### 3. Abrir el programa

- **Windows**: doble clic en `iniciar.bat`
- **macOS**: doble clic en `iniciar.command`. La primera vez puede que tengas que dar permiso: clic derecho → Abrir.

La primera vez instala lo necesario y luego abre el navegador en `http://127.0.0.1:8765`. Arrastra los documentos y listo.

Instalación manual:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uso por línea de comandos

```bash
# Procesar una carpeta completa (incluye subcarpetas)
python -m digitalizador procesar "C:\Escaneos" -o salida

# Todo a la carpeta de un postulante
python -m digitalizador procesar fotos/ --postulante "María Pérez"

# Vigilar la carpeta donde guarda el escáner y procesar lo que llegue
python -m digitalizador vigilar "C:\Escaneos" -o salida

# Interfaz web
python -m digitalizador web
```

Opciones útiles:

| Opción | Para qué |
|---|---|
| `--sin-limpieza` | Escaneos que ya vienen limpios (más rápido) |
| `--sin-recorte` | No buscar el borde de la hoja |
| `--sin-agrupar` | Dejar todo en la misma carpeta |
| `--copiar-original` | Guardar también el archivo original |
| `--forzar` | Reprocesar archivos ya procesados |
| `--idioma spa` | Cambiar idiomas del OCR (por defecto `spa+eng`, que lee mejor la `@`) |
| `--tesseract RUTA` | Si Tesseract no se encuentra solo |

## Consejos para mejores resultados

- Escanea a **300 dpi**, en escala de grises.
- Para fotos con el celular, pon la hoja sobre un fondo oscuro, con buena luz y sin flash.
- Revisa a mano los documentos con **confianza OCR menor a 60** (en la web aparecen en naranjo).

## Privacidad

Todo se procesa localmente. El `.gitignore` excluye las carpetas `salida/` y `entrada/` y los PDF e imágenes, para que **nunca se suban documentos de postulantes al repositorio**.

## Personalizar la extracción

Las reglas están en `digitalizador/extraccion.py`:

- `TIPOS`: palabras clave que definen cada tipo de documento.
- `buscar_nombre`, `buscar_ruts`, etc.: un buscador por cada campo. Para agregar uno nuevo (curso, colegio de origen, promedio…), crea una función `buscar_x` y súmala a `DatosExtraidos` y a `COLUMNAS_CSV` en `procesador.py`.

Pruebas:

```bash
pip install pytest
python -m pytest
```
