"""Línea de comandos: ``python -m controles digitalizar|consolidar``."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from . import __version__
from .cruce import EN_LISTA, armar_controles, cruzar
from .digitalizar import OpcionesDigitalizar, digitalizar
from .especialidades import Catalogo
from .fuentes import leer_agenda, leer_revision, leer_workflow, runs_de
from .informe import escribir_consolidado, escribir_digitalizados


def _cmd_digitalizar(a: argparse.Namespace) -> int:
    op = OpcionesDigitalizar(dpi=a.dpi, transcribir_con_claude=a.con_claude, modelo=a.modelo,
                             especialidades=a.especialidades)
    if a.tesseract:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = a.tesseract
    digitalizar(a.entrada, a.salida, op)
    print("Siguiente paso: completa las columnas amarillas de revision.xlsx y luego corre 'consolidar'.")
    return 0


def _cmd_consolidar(a: argparse.Namespace) -> int:
    catalogo = Catalogo.con_archivo(a.especialidades)
    filas = leer_revision(a.revision)
    controles, incompletas = armar_controles(filas, catalogo, a.especialidad or "")
    print(f"Revisión: {len(filas)} comprobantes -> {len(controles)} controles de "
          f"{len({c.run for c in controles})} pacientes ({len(incompletas)} sin RUN o sin fecha)")
    workflow = leer_workflow(a.workflow) if a.workflow else None
    if workflow is not None:
        print(f"Workflow: {len(workflow)} controles")
    agenda = leer_agenda(a.agenda, runs_de(filas)) if a.agenda else None
    cruzar(controles, workflow, agenda, catalogo=catalogo)
    por_esp = Counter(c.especialidad or "(sin especialidad)" for c in controles)
    print("Especialidades: " + ", ".join(f"{e} {n}" for e, n in por_esp.most_common()))
    a.salida.mkdir(parents=True, exist_ok=True)
    d = escribir_digitalizados(controles, a.salida / "Controles_papel_digitalizados.xlsx", incompletas)
    print(f"\n✔ {d}")
    for estado, n in Counter(c.estado for c in controles).most_common():
        print(f"   {estado:<12} {n}")
    print(f"   En lista de espera: {sum(c.estado in EN_LISTA for c in controles)}")
    if a.consolidado and workflow is not None:
        c = escribir_consolidado(controles, workflow, a.salida / "Lista_espera_controles_CONSOLIDADA.xlsx",
                                 a.workflow.name)
        print(f"✔ {c}")
    return 0


AYUDA_CSV = ("CSV con reglas extra de especialidad (columnas Especialidad;Patron); "
             "se revisan antes que el catálogo incluido")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m controles",
                                description="Digitaliza controles indicados en papel y los consolida con Workflow.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="comando", required=True)

    d = sub.add_parser("digitalizar", help="PDF de comprobantes -> revision.xlsx")
    d.add_argument("entrada", type=Path, help="carpeta o PDF con los comprobantes escaneados")
    d.add_argument("-o", "--salida", type=Path, default=Path("salida_controles"))
    d.add_argument("--dpi", type=int, default=150)
    d.add_argument("--tesseract", help="ruta a tesseract(.exe) si no está en el PATH")
    d.add_argument("--con-claude", action="store_true",
                   help="leer la indicación manuscrita con la API de Claude (requiere ANTHROPIC_API_KEY; "
                        "envía las imágenes fuera del computador)")
    d.add_argument("--modelo", default="claude-sonnet-5-5")
    d.add_argument("--especialidades", type=Path, help=AYUDA_CSV)
    d.set_defaults(func=_cmd_digitalizar)

    c = sub.add_parser("consolidar", help="revision.xlsx + Workflow + agenda -> Excel final")
    c.add_argument("revision", type=Path, help="revision.xlsx completada")
    c.add_argument("--workflow", type=Path, help="Excel de controles exportado de Workflow (Controles_AAAA-MM-DD.xlsx)")
    c.add_argument("--agenda", type=Path, nargs="*", default=[],
                   help="carpetas o archivos de reportes de agenda (HCVB_ext_*.xls o CSV del extractor de agenda)")
    c.add_argument("--consolidado", action="store_true",
                   help="generar también Lista_espera_controles_CONSOLIDADA.xlsx (Workflow + papel)")
    c.add_argument("--especialidad", help="especialidad a usar cuando el Local del comprobante no la indica")
    c.add_argument("--especialidades", type=Path, help=AYUDA_CSV)
    c.add_argument("-o", "--salida", type=Path, default=Path("salida_controles"))
    c.set_defaults(func=_cmd_consolidar)

    a = p.parse_args(argv)
    return a.func(a)
