"""
cargar_tabuladores_reales.py
─────────────────────────────────────────────────────────────────────────────
Carga el Tabulador Oficial de la clínica INTRA en la base de datos.
Datos extraídos directamente del documento:
    Relacionserviciosytabuladores.docx

Idempotente: usa update_or_create → seguro de ejecutar múltiples veces.
Si un terapeuta del documento no existe aún en la BD, lo crea con activo=True.

Uso:
    python cargar_tabuladores_reales.py
    railway run python cargar_tabuladores_reales.py   ← producción
"""

import os
import sys
from decimal import Decimal

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from clinica.models import Terapeuta, TabuladorGeneral, ReglaTerapeuta


# =============================================================================
# TABULADOR GENERAL — Categorías 0 a 11
# =============================================================================
# Fuente: sección "Tabulador general" del Word.
# Campos: numero, descripcion, pago_base, pago_consultorio_propio,
#         bono_monto (monto del bono de volumen), bono_umbral_pacientes
#
# Nota: el bono en categorías 1-3 está descrito como "gasolina" en el Word,
# pero se modela igual que cualquier bono de umbral en TabuladorGeneral.

TABULADOR_GENERAL = [
    {
        "numero": 0,
        "descripcion": (
            "Practicante en formación en psicoterapia con "
            "titulación universitaria y supervisión."
        ),
        "pago_base": Decimal("60.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 1,
        "descripcion": (
            "Titulación universitaria + 1 curso o diplomado "
            "relacionado con el área de trabajo."
        ),
        "pago_base": Decimal("100.00"),
        "pago_consultorio_propio": None,
        "bono_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
    },
    {
        "numero": 2,
        "descripcion": (
            "Titulación universitaria + 1 maestría o especialidad en curso."
        ),
        "pago_base": Decimal("110.00"),
        "pago_consultorio_propio": None,
        "bono_monto": Decimal("300.00"),
        "bono_umbral_pacientes": 5,
    },
    {
        "numero": 3,
        "descripcion": (
            "Titulación universitaria + maestría o especialidad concluida "
            "en área relacionada con psicoterapia."
        ),
        "pago_base": Decimal("180.00"),
        "pago_consultorio_propio": None,
        "bono_monto": Decimal("400.00"),
        "bono_umbral_pacientes": 5,
    },
    {
        "numero": 4,
        "descripcion": (
            "Titulación universitaria en medicina + formación en salud mental."
        ),
        "pago_base": Decimal("300.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 5,
        "descripcion": (
            "Titulación universitaria en medicina + "
            "especialidad en psiquiatría en curso."
        ),
        "pago_base": Decimal("450.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 6,
        "descripcion": (
            "Titulación universitaria en medicina + "
            "especialidad en psiquiatría concluida."
        ),
        "pago_base": Decimal("600.00"),            # consultorio INTRA
        "pago_consultorio_propio": Decimal("700.00"),  # consultorio del médico
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 7,
        "descripcion": (
            "Titulación universitaria en nutrición + formación clínica."
        ),
        "pago_base": Decimal("425.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 8,
        "descripcion": (
            "Titulación universitaria en nutrición + maestría."
        ),
        "pago_base": Decimal("500.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 9,
        "descripcion": "Formación en tanatología clínica.",
        "pago_base": Decimal("110.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 10,
        "descripcion": "Atención infantil.",
        "pago_base": Decimal("200.00"),
        "pago_consultorio_propio": None,
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
    {
        "numero": 11,
        "descripcion": "Médico estudiante de especialidad.",
        "pago_base": Decimal("450.00"),            # consultorio INTRA
        "pago_consultorio_propio": Decimal("500.00"),  # consultorio propio
        "bono_monto": None,
        "bono_umbral_pacientes": None,
    },
]


# =============================================================================
# TABULADORES INDIVIDUALES — 15 profesionales
# =============================================================================
# Fuente: sección "Tabuladores individuales por profesional" del Word.
#
# Mapeo columnas Word → campos ReglaTerapeuta:
#   "Pago por paciente" → pago_por_sesion  (tarifa plana; aplica a la mayoría)
#   "Pago individual"   → pago_individual  (solo María Amancio)
#   "Pago en pareja"    → pago_pareja      (solo María Amancio)
#   "Bono"              → bono_umbral_monto + bono_umbral_pacientes
#   Bono supervisor     → bono_por_paciente (solo José Arcadio: +$25/pac.)
#   "Nota relevante"    → notas

TERAPEUTAS_REGLAS = [
    # ── Licenciatura, bono estándar $100 c/5 pacientes ────────────────────────
    {
        "nombre": "Alejandra Durán",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Ana Juárez",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Daniela Sarmiento",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Fabiola Fragoso",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": (
            "En evaluaciones: reportar una hora adicional de "
            "elaboración de informe como BonoExtra manual."
        ),
    },
    {
        "nombre": "Jennifer Torres",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Magda Charles",
        "pago_por_sesion": Decimal("200.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Perla Realme",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Rossy Macías",
        "pago_por_sesion": Decimal("150.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("100.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    # ── Casos especiales ──────────────────────────────────────────────────────
    {
        "nombre": "Benjamín Villagómez",
        "pago_por_sesion": Decimal("215.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": None,
        "bono_umbral_pacientes": None,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Enrique Luna",
        "pago_por_sesion": Decimal("600.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": None,
        "bono_umbral_pacientes": None,
        "bono_por_paciente": None,
        "notas": "Médico. Sin bono de volumen.",
    },
    {
        "nombre": "Esmeralda Colunga",
        "pago_por_sesion": Decimal("220.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("200.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "Gloria Sarmiento",
        "pago_por_sesion": Decimal("60.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": None,
        "bono_umbral_pacientes": None,
        "bono_por_paciente": None,
        "notas": (
            "Practicante. En evaluaciones: reportar hora adicional "
            "de elaboración de informe como BonoExtra manual."
        ),
    },
    {
        "nombre": "José Arcadio",
        "pago_por_sesion": Decimal("200.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("400.00"),
        "bono_umbral_pacientes": 5,
        "bono_por_paciente": Decimal("25.00"),   # bono supervisor
        "notas": (
            "Maestría en Psicología de la Salud. "
            "Bono supervisor: $25 adicionales por cada paciente atendido en el periodo."
        ),
    },
    {
        "nombre": "Lucía Sánchez",
        "pago_por_sesion": Decimal("185.00"),
        "pago_individual": None,
        "pago_pareja": None,
        "bono_umbral_monto": Decimal("400.00"),
        "bono_umbral_pacientes": 7,              # umbral de 7, no 5
        "bono_por_paciente": None,
        "notas": "En caso de realizar evaluaciones, registrar como BonoExtra manual.",
    },
    {
        "nombre": "María Amancio",
        "pago_por_sesion": None,                 # No aplica tarifa plana
        "pago_individual": Decimal("350.00"),
        "pago_pareja": Decimal("400.00"),
        "bono_umbral_monto": None,
        "bono_umbral_pacientes": None,
        "bono_por_paciente": None,
        "notas": (
            "Licenciatura + Master en Terapia Sexual y de Pareja. "
            "Tarifa diferenciada: individual $350 / pareja-familiar $400. "
            "Sin tarifa plana (pago_por_sesion = None)."
        ),
    },
]


# =============================================================================
# EJECUCIÓN
# =============================================================================

def main():
    w = 65
    print("=" * w)
    print("  CARGA DE TABULADORES OFICIALES — Clinica INTRA")
    print("  Fuente: Relacionserviciosytabuladores.docx")
    print("=" * w)

    # ── 1. Tabulador General ──────────────────────────────────────────────────
    print(f"\n[1/2] Tabulador General ({len(TABULADOR_GENERAL)} categorias 0-11)...\n")
    for cat in TABULADOR_GENERAL:
        bono = (
            f"${cat['bono_monto']}/c{cat['bono_umbral_pacientes']}pac"
            if cat["bono_monto"] else "sin bono"
        )
        cp = f" | cpropio ${cat['pago_consultorio_propio']}" if cat["pago_consultorio_propio"] else ""
        obj, created = TabuladorGeneral.objects.update_or_create(
            numero=cat["numero"],
            defaults={
                "descripcion":             cat["descripcion"],
                "pago_base":               cat["pago_base"],
                "pago_consultorio_propio": cat["pago_consultorio_propio"],
                "bono_monto":              cat["bono_monto"],
                "bono_umbral_pacientes":   cat["bono_umbral_pacientes"],
            },
        )
        estado = "CREADO  " if created else "actualiz"
        print(f"  Cat {cat['numero']:>2}  ${cat['pago_base']:>7}{cp:<22}  {bono:<30}  [{estado}]")

    # ── 2. Terapeutas + ReglaTerapeuta ────────────────────────────────────────
    print(f"\n[2/2] Terapeutas y Reglas de Pago ({len(TERAPEUTAS_REGLAS)} profesionales)...\n")
    nuevos = 0
    for datos in TERAPEUTAS_REGLAS:
        terapeuta, t_new = Terapeuta.objects.get_or_create(
            nombre=datos["nombre"],
            defaults={"activo": True},
        )
        if t_new:
            nuevos += 1

        _, r_new = ReglaTerapeuta.objects.update_or_create(
            terapeuta=terapeuta,
            defaults={
                "pago_por_sesion":       datos["pago_por_sesion"],
                "pago_individual":       datos["pago_individual"],
                "pago_pareja":           datos["pago_pareja"],
                "bono_umbral_monto":     datos["bono_umbral_monto"],
                "bono_umbral_pacientes": datos["bono_umbral_pacientes"],
                "bono_por_paciente":     datos["bono_por_paciente"],
                "notas":                 datos["notas"],
            },
        )

        if datos["pago_por_sesion"]:
            base = f"${datos['pago_por_sesion']}/ses"
        else:
            base = f"ind ${datos['pago_individual']} / par ${datos['pago_pareja']}"

        t_flag = "  <-- TERAPEUTA NUEVO" if t_new else ""
        r_flag = "regla CREADA    " if r_new else "regla actualizada"
        print(f"  {datos['nombre']:<26}  {base:<26}  [{r_flag}]{t_flag}")

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n  Categorias de tabulador cargadas : {len(TABULADOR_GENERAL)}")
    print(f"  Terapeutas nuevos en BD          : {nuevos}")
    print(f"  Terapeutas ya existentes         : {len(TERAPEUTAS_REGLAS) - nuevos}")
    print("\n" + "=" * w)
    print("  Tabuladores cargados correctamente.")
    print("=" * w + "\n")


if __name__ == "__main__":
    main()
