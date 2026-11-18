"""Digitalización de controles indicados en papel (comprobantes de citación)
y consolidación con la lista de espera de Workflow y la agenda de Experto.

Flujo en dos pasos:

1. ``python -m controles digitalizar PDFs/ -o salida``
   Lee los comprobantes escaneados, extrae los datos impresos con OCR y
   genera ``salida/revision.xlsx`` para completar (o revisar) la indicación
   manuscrita de cada comprobante.

2. ``python -m controles consolidar salida/revision.xlsx --workflow ... --agenda ...``
   Cruza los controles con Workflow y con las citas de la agenda y genera
   el Excel final con la lista de espera real.
"""

__version__ = "0.1.0"
