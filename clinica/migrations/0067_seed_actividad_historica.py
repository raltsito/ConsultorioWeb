from datetime import datetime, timezone as dt_tz
from django.db import migrations


def seed_actividad(apps, schema_editor):
    RegistroActividad       = apps.get_model('clinica', 'RegistroActividad')
    BloqueoAgendaTerapeuta  = apps.get_model('clinica', 'BloqueoAgendaTerapeuta')
    PacienteTerapeutaAcceso = apps.get_model('clinica', 'PacienteTerapeutaAcceso')
    CorteSemanal            = apps.get_model('clinica', 'CorteSemanal')
    SolicitudReagendo       = apps.get_model('clinica', 'SolicitudReagendo')
    Paciente                = apps.get_model('clinica', 'Paciente')
    ReporteIncidente        = apps.get_model('clinica', 'ReporteIncidente')
    SolicitudHorasExpositor = apps.get_model('clinica', 'SolicitudHorasExpositor')

    batch = []

    for b in BloqueoAgendaTerapeuta.objects.select_related('terapeuta', 'creado_por').all():
        ter = b.terapeuta.nombre if b.terapeuta else 'Sin terapeuta'
        tipo = 'Temporal' if b.tipo_bloqueo == 'temporal' else 'Permanente'
        fecha_str = b.fecha_inicio.strftime('%d/%m/%Y') if b.fecha_inicio else '?'
        desc = f'Bloqueo {tipo.lower()} de agenda creado para {ter} desde {fecha_str}.'
        if b.motivo:
            desc += f' Motivo: {b.motivo}.'
        batch.append(RegistroActividad(
            usuario_id=b.creado_por_id,
            accion='bloqueo_creado',
            categoria='disponibilidad',
            descripcion=desc,
            terapeuta_afectado_id=b.terapeuta_id,
            es_retroactivo=True,
            timestamp=b.creado_en,
        ))

    for a in PacienteTerapeutaAcceso.objects.select_related('terapeuta', 'paciente', 'creado_por').all():
        ter = a.terapeuta.nombre if a.terapeuta else '?'
        pac = a.paciente.nombre if a.paciente else '?'
        batch.append(RegistroActividad(
            usuario_id=a.creado_por_id,
            accion='paciente_registrado',
            categoria='paciente',
            descripcion=f'Acceso de terapeuta vinculado: {ter} ↔ {pac}.',
            terapeuta_afectado_id=a.terapeuta_id,
            paciente_afectado_id=a.paciente_id,
            es_retroactivo=True,
            timestamp=a.creado_en,
        ))

    for c in CorteSemanal.objects.filter(estatus__in=['aprobado', 'pagado']).select_related('terapeuta', 'aprobado_por').all():
        if not c.aprobado_en:
            continue
        ter = c.terapeuta.nombre if c.terapeuta else '?'
        fi = c.fecha_inicio.strftime('%d/%m/%Y') if c.fecha_inicio else '?'
        ff = c.fecha_fin.strftime('%d/%m/%Y') if c.fecha_fin else '?'
        batch.append(RegistroActividad(
            usuario_id=c.aprobado_por_id,
            accion='nomina_aprobada',
            categoria='nomina',
            descripcion=f'Nómina de {ter} del {fi} al {ff} aprobada. Total: ${c.total_pago}.',
            terapeuta_afectado_id=c.terapeuta_id,
            es_retroactivo=True,
            timestamp=c.aprobado_en,
        ))

    for sr in SolicitudReagendo.objects.select_related('terapeuta', 'cita__paciente').all():
        ter = sr.terapeuta.nombre if sr.terapeuta else '?'
        pac_id = sr.cita.paciente_id if sr.cita else None
        pac = sr.cita.paciente.nombre if (sr.cita and sr.cita.paciente) else '?'
        fp = sr.fecha_propuesta.strftime('%d/%m/%Y') if sr.fecha_propuesta else '?'
        hp = sr.hora_propuesta.strftime('%H:%M') if sr.hora_propuesta else '?'
        batch.append(RegistroActividad(
            accion='reagendo_solicitado',
            categoria='reagendo',
            descripcion=f'{ter} solicitó reagendar la cita de {pac} al {fp} a las {hp}.',
            terapeuta_afectado_id=sr.terapeuta_id,
            paciente_afectado_id=pac_id,
            es_retroactivo=True,
            timestamp=sr.creado_en,
        ))
        if sr.estado == 'aprobada':
            batch.append(RegistroActividad(
                accion='reagendo_aprobado',
                categoria='reagendo',
                descripcion=f'Reagendo de {ter} para {pac} aprobado. Nueva fecha: {fp} a las {hp}.',
                terapeuta_afectado_id=sr.terapeuta_id,
                paciente_afectado_id=pac_id,
                es_retroactivo=True,
                timestamp=sr.creado_en,
            ))
        elif sr.estado == 'rechazada':
            batch.append(RegistroActividad(
                accion='reagendo_rechazado',
                categoria='reagendo',
                descripcion=f'Reagendo de {ter} para {pac} rechazado.',
                terapeuta_afectado_id=sr.terapeuta_id,
                paciente_afectado_id=pac_id,
                es_retroactivo=True,
                timestamp=sr.creado_en,
            ))

    for p in Paciente.objects.all():
        batch.append(RegistroActividad(
            accion='paciente_registrado',
            categoria='paciente',
            descripcion=f'Expediente de {p.nombre} registrado en el sistema.',
            paciente_afectado_id=p.pk,
            es_retroactivo=True,
            timestamp=p.fecha_registro,
        ))

    for inc in ReporteIncidente.objects.select_related('terapeuta').all():
        ter = inc.terapeuta.nombre if inc.terapeuta else '?'
        tipo_map = {'queja': 'queja', 'sugerencia': 'sugerencia', 'incidente': 'incidente en consultorio'}
        tipo_str = tipo_map.get(inc.tipo, inc.tipo)
        batch.append(RegistroActividad(
            accion='incidente_reportado',
            categoria='incidente',
            descripcion=f'{ter} reportó una {tipo_str}: "{inc.titulo}".',
            terapeuta_afectado_id=inc.terapeuta_id,
            es_retroactivo=True,
            timestamp=inc.fecha_creacion,
        ))
        if inc.respuesta and inc.respuesta_fecha:
            batch.append(RegistroActividad(
                accion='incidente_respondido',
                categoria='incidente',
                descripcion=f'Incidente "{inc.titulo}" de {ter} respondido.',
                terapeuta_afectado_id=inc.terapeuta_id,
                es_retroactivo=True,
                timestamp=inc.respuesta_fecha,
            ))

    for sh in SolicitudHorasExpositor.objects.filter(estado__in=['aceptada', 'rechazada']).select_related('terapeuta').all():
        ter = sh.terapeuta.nombre if sh.terapeuta else '?'
        estado_str = 'aceptada' if sh.estado == 'aceptada' else 'rechazada'
        batch.append(RegistroActividad(
            accion='expositor_respondido',
            categoria='nomina',
            descripcion=f'Solicitud de {sh.horas}h expositor de {ter} en "{sh.lugar}" {estado_str}.',
            terapeuta_afectado_id=sh.terapeuta_id,
            es_retroactivo=True,
            timestamp=sh.creado_en,
        ))

    CHUNK = 500
    for i in range(0, len(batch), CHUNK):
        RegistroActividad.objects.bulk_create(batch[i:i + CHUNK])


def reverse_seed(apps, schema_editor):
    RegistroActividad = apps.get_model('clinica', 'RegistroActividad')
    RegistroActividad.objects.filter(es_retroactivo=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0066_registro_actividad'),
    ]

    operations = [
        migrations.RunPython(seed_actividad, reverse_seed),
    ]
