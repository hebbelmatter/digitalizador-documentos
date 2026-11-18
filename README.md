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

---

# Controles en papel → lista de espera (todas las especialidades)

Antes del 21/07/2025, los médicos indicaban el próximo control a mano sobre el **comprobante de citación**. Por eso esos controles no están en Workflow. El módulo `controles` los digitaliza, los cruza con Workflow y con la agenda de Experto, y genera la **lista de espera real**. Todo corre en tu computador.

Es un proceso de dos pasos:

```
 PDF escaneados ──► 1. digitalizar ──► revision.xlsx ──(se revisa/completa)──┐
                                                                             ▼
 Workflow (Controles_AAAA-MM-DD.xlsx) + reportes de agenda ──► 2. consolidar ──► Excel final
```

### 1. Digitalizar

```bash
python -m controles digitalizar "CARPETA_CON_PDF" -o salida_controles
```

- Endereza cada página y lee con OCR los datos impresos: RUN (valida el dígito verificador), nombre, fecha y hora de citación, local y profesional.
- Deduce la **especialidad** a partir del local (p. ej. `HCVB-CC-NEUROC. COLUMNA COMPLEJA` → NEUROCIRUGÍA). Puedes mezclar en la misma carpeta PDF de distintas especialidades.
- Si una hoja trae dos comprobantes, crea una fila para cada uno.
- Genera `salida_controles/revision.xlsx` y guarda en `salida_controles/imagenes/` la mitad superior de cada comprobante, que es donde está lo escrito a mano.

**Revisión:** abre `revision.xlsx` y completa las **columnas amarillas** mirando la imagen (la columna *Imagen* tiene el enlace):

| Columna | Qué poner |
|---|---|
| Indicación manuscrita | Lo que escribió el médico, p. ej. `Control 3 meses con resonancia`. El plazo se calcula solo a partir de `3 meses`, `30 días`, `1 año`, `anual` o `abril 2026` |
| Plazo (meses) / Mes indicado | Sólo si quieres forzar el plazo |
| Fecha citación corregida, RUN corregido, Nombre corregido | Sólo si el impreso está mal o fue corregido a mano |
| Especialidad corregida | Sólo si la columna *Especialidad* quedó vacía o equivocada |
| Anotaciones de contacto | Llamados, `NSP`, fonos nuevos, etc. |
| Excluir (S/N) | `S` para hojas sin paciente o que no se deben contar |

Si vuelves a correr `digitalizar` (por ejemplo, al agregar PDF nuevos), lo que ya completaste se conserva.

**Opcional: lectura automática del manuscrito.** Con `--con-claude`, la indicación manuscrita se transcribe con la API de Claude. Requiere la variable `ANTHROPIC_API_KEY`. Advertencia: esta opción **envía las imágenes, que contienen datos del paciente, fuera del computador**, así que úsala sólo si la institución lo autoriza. Aunque la uses, revisa las lecturas que quedan marcadas con `(?)`.

### 2. Consolidar

```bash
python -m controles consolidar salida_controles/revision.xlsx \
    --workflow "Controles_2026-11-16.xlsx" \
    --agenda "CARPETA_REPORTES_AGENDA" \
    -o salida_controles
```

`--agenda` acepta varias carpetas o archivos:

- los `HCVB_ext_*.xls` descargados de Experto;
- los CSV del extractor de agenda del monorepo `hcvb-analisis-datos`: `reporte_agenda_historico_AAAA_bloque_NN.csv` y `reporte_agenda_60dias_*.csv`.

Las descargas vacías (`Página no encontrada`) se omiten solas. Si un `.xls` viene dañado y tienes LibreOffice instalado, se lee con LibreOffice.

Resultado de cada control en papel:

| Estado | Criterio | ¿En lista de espera? |
|---|---|---|
| PENDIENTE | Sin atención posterior de la misma especialidad (incluye citados que no asistieron o con hora cancelada/bloqueada) | Sí |
| AGENDADA | Tiene una cita futura de la misma especialidad | Sí |
| EN WORKFLOW | El mismo control ya está en Workflow (misma fecha de atención ±1 día) | No (evita duplicar) |
| ATENDIDA | Tuvo una atención posterior de la misma especialidad (agenda) o una atención posterior registrada en Workflow | No |
| REEMPLAZADA | El paciente tiene un comprobante en papel más reciente | No |
| NO REQUIERE | La indicación dice alta, ingreso a LEQ o comprobante anulado | No |

Se generan dos archivos en `salida_controles/`:

1. **`Controles_papel_digitalizados.xlsx`**, con estas hojas:
   - *Resumen* (con fórmulas)
   - *Digitalizados* (todos los comprobantes)
   - *Lista de espera* (sólo PENDIENTE y AGENDADA, con las 12 columnas de Workflow)
   - *Cruce atenciones*
   - *Detalle digitalización*
   - *Sin RUN o sin fecha*, si hay comprobantes incompletos
2. **`Lista_espera_controles_CONSOLIDADA.xlsx`**: Workflow + controles en papel en lista de espera, con la columna *Origen* y un resumen por especialidad y por profesional.

### Especialidades

Cada control se cruza **sólo con citas y controles de su propia especialidad**: un control de traumatología no se da por atendido con una cita de cardiología. La especialidad de cada agenda de Experto se deduce de su nombre con las mismas reglas que el local del comprobante. Las reglas están en `controles/especialidades.py` e incluyen las especialidades más comunes.

Si una especialidad no se reconoce o los nombres de las agendas de tu hospital son distintos, tienes dos opciones:

- `--especialidad TRAUMATOLOGÍA` en `consolidar`: se usa para los comprobantes cuyo local no indica la especialidad.
- `--especialidades reglas.csv` (en `digitalizar` y `consolidar`): agrega reglas propias, que se revisan antes que las incluidas. El patrón es una expresión regular sobre el texto en mayúsculas y sin tildes:

```
Especialidad;Patron
TRAUMATOLOGÍA;TRAUMA|COT\b
CIRUGÍA DE MAMA;MAMA
```

Un control sin especialidad reconocida se cruza sólo con las citas de su mismo local y queda marcado en *Observación*.

**Cobertura:** el cruce sólo ve las citas de los reportes de agenda que entregues. Si un comprobante es anterior al primer reporte (p. ej., de 2023, cuando la agenda parte en 2025), la hoja *Cruce atenciones* lo marca como cobertura **parcial**. Para cubrir esos años, descarga los años que faltan con el extractor de agenda (modo `historico`).

### Doble clic

- **macOS**: `controles.command`
- **Windows**: `controles.bat`

Ambos preparan el entorno la primera vez y preguntan qué paso quieres correr.

### Privacidad

El `.gitignore` excluye `salida_controles/` y todos los `.xlsx`, `.xls` y `.csv`, para que **nunca se suban planillas con RUT o datos clínicos**. Las pruebas (`tests/test_controles.py`) usan sólo datos inventados.
