"""
generar_datos_demo.py
─────────────────────────────────────────────────────────────────────────────
Script standalone para poblar la BD con datos de prueba del módulo de Nómina.
Seguro para correr múltiples veces: usa get_or_create en todos los registros.

NOTA ARQUITECTÓNICA sobre BonoExtra:
  El modelo real NO tiene FK directa a Terapeuta ni campo fecha_evento.
  BonoExtra está ligado a un CorteSemanal (que sí pertenece a un Terapeuta).
  El script crea primero el CorteSemanal en borrador y luego adjunta el bono.

Uso:
  python generar_datos_demo.py
"""

import os
import sys
import django
from datetime import date, time, timedelta
from decimal import Decimal

# ─── Bootstrap Django ─────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# ─── Imports de modelos y servicios ──────────────────────────────────────────
from clinica.models import (
    Terapeuta, Paciente, Servicio, Cita,
    ReglaTerapeuta, CorteSemanal, BonoExtra,
)
from clinica.services import calcular_nomina_semanal


# =============================================================================
# UTILIDADES
# =============================================================================

def semana_pasada():
    """Retorna (lunes, domingo) de la semana calendario anterior."""
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    return lunes, lunes + timedelta(days=6)


def dia_semana(lunes, offset):
    """lunes + N días. offset 0=lun, 1=mar, 2=mié, 3=jue, 4=vie, 5=sáb."""
    return lunes + timedelta(days=offset)


def crear_cita(terapeuta, paciente, servicio, fecha, hora_h, costo=None, metodo="Efectivo"):
    """
    Crea una cita con estatus si_asistio usando get_or_create.
    Clave de búsqueda: (terapeuta, paciente, fecha, hora) — suficiente para
    garantizar idempotencia en este dataset controlado.
    """
    cita, creada = Cita.objects.get_or_create(
        terapeuta=terapeuta,
        paciente=paciente,
        fecha=fecha,
        hora=time(hora_h, 0),
        defaults={
            "servicio": servicio,
            "estatus": Cita.ESTATUS_SI_ASISTIO,
            "tipo_paciente": Cita.TIPO_SEGUIMIENTO,
            "costo": Decimal(str(costo)) if costo is not None else None,
            "metodo_pago": metodo,
        },
    )
    return cita, creada


def seccion(titulo):
    ancho = 60
    print(f"\n{'-' * ancho}")
    print(f"  {titulo}")
    print(f"{'-' * ancho}")


# =============================================================================
# SCRIPT PRINCIPAL
# =============================================================================

def main():
    lunes, domingo = semana_pasada()
    print(f"\n{'=' * 60}")
    print(f"  GENERADOR DE DATOS DEMO - Modulo Nomina")
    print(f"  Semana: {lunes.strftime('%d/%m/%Y')} al {domingo.strftime('%d/%m/%Y')}")
    print(f"{'=' * 60}")

    # ─── 1. Servicios base ────────────────────────────────────────────────────
    seccion("1 / Servicios")
    svc_ind, _   = Servicio.objects.get_or_create(nombre="Psicoterapia individual")
    svc_par, _   = Servicio.objects.get_or_create(nombre="Psicoterapia de pareja")
    print(f"  [OK] '{svc_ind.nombre}'")
    print(f"  [OK] '{svc_par.nombre}'")

    # ─── 2. Pacientes dummy ───────────────────────────────────────────────────
    seccion("2 / Pacientes demo")
    pacientes = []
    for i in range(1, 11):
        p, creado = Paciente.objects.get_or_create(
            nombre=f"Paciente Demo {i}",
            defaults={
                "fecha_nacimiento": date(1990, 1, 1),
                "telefono": "0000000000",
                "sexo": "Femenino",
                "servicio_inicial": svc_ind,
            },
        )
        pacientes.append(p)
    print(f"  [OK] {len(pacientes)} pacientes listos (Paciente Demo 1 … 10)")

    # ─── 3. Alejandra Durán — Caso Volumen ───────────────────────────────────
    seccion("3 / Alejandra Durán — Caso Volumen")
    ale, _ = Terapeuta.objects.get_or_create(
        nombre="Alejandra Durán",
        defaults={"activo": True},
    )
    ReglaTerapeuta.objects.get_or_create(
        terapeuta=ale,
        defaults={
            "pago_por_sesion":      Decimal("150.00"),
            "bono_umbral_monto":    Decimal("100.00"),
            "bono_umbral_pacientes": 5,
            "notas": "Demo: bono de $100 al alcanzar 5 sesiones semanales.",
        },
    )

    agenda_ale = [
        (pacientes[0], dia_semana(lunes, 0), 9),   # lunes
        (pacientes[1], dia_semana(lunes, 1), 10),  # martes
        (pacientes[2], dia_semana(lunes, 2), 11),  # miércoles
        (pacientes[3], dia_semana(lunes, 3), 14),  # jueves
        (pacientes[4], dia_semana(lunes, 4), 16),  # viernes
    ]
    for pac, fecha, hora in agenda_ale:
        _, creada = crear_cita(ale, pac, svc_ind, fecha, hora)
        estado = "nueva" if creada else "ya existía"
        print(f"  {'[OK]' if creada else '--'} Cita {fecha} {hora:02d}:00 — {estado}")

    # ─── 4. José Arcadio — Caso Híbrido Complejo ─────────────────────────────
    seccion("4 / José Arcadio — Caso Híbrido Complejo")
    jose, _ = Terapeuta.objects.get_or_create(
        nombre="José Arcadio",
        defaults={"activo": True},
    )
    ReglaTerapeuta.objects.get_or_create(
        terapeuta=jose,
        defaults={
            "pago_por_sesion":       Decimal("200.00"),
            "bono_umbral_monto":     Decimal("400.00"),
            "bono_umbral_pacientes": 5,
            "bono_por_paciente":     Decimal("25.00"),
            "notas": "Demo: bono de volumen $400 c/5 sesiones + $25 por paciente (supervisor).",
        },
    )

    agenda_jose = [
        (pacientes[0], dia_semana(lunes, 0), 10),  # lunes
        (pacientes[1], dia_semana(lunes, 1), 11),  # martes
        (pacientes[2], dia_semana(lunes, 2),  9),  # miércoles
        (pacientes[3], dia_semana(lunes, 3), 15),  # jueves
        (pacientes[4], dia_semana(lunes, 4), 12),  # viernes
        (pacientes[5], dia_semana(lunes, 5), 10),  # sábado
    ]
    for pac, fecha, hora in agenda_jose:
        _, creada = crear_cita(jose, pac, svc_ind, fecha, hora)
        estado = "nueva" if creada else "ya existía"
        print(f"  {'[OK]' if creada else '--'} Cita {fecha} {hora:02d}:00 — {estado}")

    # ─── 5. María Amancio — Caso Excepción Fija ──────────────────────────────
    seccion("5 / María Amancio — Caso Excepción Fija")
    maria, _ = Terapeuta.objects.get_or_create(
        nombre="María Amancio",
        defaults={"activo": True},
    )
    ReglaTerapeuta.objects.get_or_create(
        terapeuta=maria,
        defaults={
            # pago_por_sesion = None intencionalmente (no aplica tarifa plana)
            "pago_individual": Decimal("350.00"),
            "pago_pareja":     Decimal("400.00"),
            "notas": "Demo: tarifa diferenciada individual/pareja. Sin pago_por_sesion.",
        },
    )

    # Cita individual (pago_individual=350 vía _resolver_monto_sesion)
    cita_ind, creada_ind = crear_cita(
        maria, pacientes[6], svc_ind, dia_semana(lunes, 0), 11
    )
    print(f"  {'[OK]' if creada_ind else '--'} Cita individual {cita_ind.fecha} 11:00 — {'nueva' if creada_ind else 'ya existía'}")

    # Cita de pareja (pago_pareja=400 se activa cuando hay pacientes_adicionales)
    cita_par, creada_par = crear_cita(
        maria, pacientes[7], svc_par, dia_semana(lunes, 2), 13
    )
    if creada_par:
        # Añadir el segundo integrante de la pareja como paciente adicional
        cita_par.pacientes_adicionales.add(pacientes[8])
        print(f"  [OK] Cita pareja {cita_par.fecha} 13:00 + Paciente Demo 9 como adicional")
    else:
        print(f"  -- Cita pareja {cita_par.fecha} 13:00 — ya existía")

    # ─── 6. Fabiola Fragoso — Caso Evento Manual ─────────────────────────────
    seccion("6 / Fabiola Fragoso — Caso Evento Manual")
    fabiola, _ = Terapeuta.objects.get_or_create(
        nombre="Fabiola Fragoso",
        defaults={"activo": True},
    )
    ReglaTerapeuta.objects.get_or_create(
        terapeuta=fabiola,
        defaults={
            "pago_por_sesion": Decimal("150.00"),
            "notas": "Demo: caso de bono extra manual por elaboración de informe.",
        },
    )

    cita_fab, creada_fab = crear_cita(
        fabiola, pacientes[9], svc_ind, dia_semana(lunes, 0), 12
    )
    print(f"  {'[OK]' if creada_fab else '--'} Cita {cita_fab.fecha} 12:00 — {'nueva' if creada_fab else 'ya existía'}")

    # BonoExtra requiere un CorteSemanal existente (diseño del modelo real).
    # Creamos el corte en borrador para que el bono quede adjunto antes del cálculo.
    corte_fab, corte_creado = CorteSemanal.objects.get_or_create(
        terapeuta=fabiola,
        fecha_inicio=lunes,
        defaults={
            "fecha_fin": domingo,
            "estatus": CorteSemanal.ESTATUS_BORRADOR,
        },
    )
    bono, bono_creado = BonoExtra.objects.get_or_create(
        corte=corte_fab,
        concepto="Elaboración de informe",
        defaults={"monto": Decimal("150.00")},
    )
    if bono_creado:
        print(f"  [OK] BonoExtra 'Elaboración de informe' $150 adjunto al corte")
    else:
        print(f"  -- BonoExtra ya existía en el corte")

    # ─── 7. Calcular cortes semanales para todos ──────────────────────────────
    seccion("7 / Calculando cortes semanales")
    print("  (Usa calcular_nomina_semanal() del servicio real)\n")

    resumen = []
    for terapeuta in [ale, jose, maria, fabiola]:
        try:
            corte = calcular_nomina_semanal(terapeuta, lunes, domingo)
            resumen.append((terapeuta.nombre, corte.total_sesiones, corte.subtotal_sesiones, corte.total_bonos, corte.total_pago))
            print(
                f"  [OK] {terapeuta.nombre:<22} "
                f"{corte.total_sesiones} ses.  "
                f"base ${corte.subtotal_sesiones:>8.2f}  "
                f"bonos ${corte.total_bonos:>7.2f}  "
                f"=> TOTAL ${corte.total_pago:>8.2f}"
            )
        except Exception as exc:
            print(f"  [ERR] {terapeuta.nombre}: {exc}")

    # --- Resumen final -------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  RESUMEN DE NOMINA DEMO")
    print(f"{'=' * 60}")
    total_global = Decimal("0.00")
    for nombre, sesiones, base, bonos, total in resumen:
        print(f"  {nombre:<22}  {sesiones:>2} ses   ${total:>8.2f}")
        total_global += total
    print(f"{'-' * 60}")
    print(f"  {'TOTAL NOMINA SEMANAL':22}          ${total_global:>8.2f}")
    print(f"{'=' * 60}")

    print("\n¡Base de datos lista para el Demo!\n")


if __name__ == "__main__":
    main()
