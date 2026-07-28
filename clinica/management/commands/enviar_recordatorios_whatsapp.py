from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from clinica.models import Cita, ConfiguracionWhatsApp, MensajeWhatsApp
from clinica import services_whatsapp as wa


class Command(BaseCommand):
    help = 'Envía recordatorios y encuestas de citas por WhatsApp'

    def handle(self, *args, **options):
        if not ConfiguracionWhatsApp.get_actual().automatizacion_activa:
            self.stdout.write(self.style.WARNING(
                'Automatización desactivada: no se enviaron mensajes automáticos.'))
            return

        hoy = timezone.localdate()

        # --- Recordatorio 5 días ---
        for cita in self._citas_activas(hoy + timedelta(days=5)).filter(
                recordatorio_5d_enviado_en__isnull=True):
            self._enviar(cita, MensajeWhatsApp.TIPO_RECORDATORIO_5D, 'recordatorio_cita_5_dias',
                lambda d: [d['nombre_paciente'], d['fecha'], d['hora'],
                           d['sucursal'], d['terapeuta'], d['servicio']])

        # --- Recordatorio 3 días ---
        for cita in self._citas_activas(hoy + timedelta(days=3)).filter(
                recordatorio_3d_enviado_en__isnull=True):
            self._enviar(cita, MensajeWhatsApp.TIPO_RECORDATORIO_3D, 'recordatorio_cita_3_dias',
                lambda d: [d['nombre_paciente'], d['fecha'], d['hora'],
                           d['sucursal'], d['terapeuta'], d['servicio']])

        # --- Confirmación 1 día antes ---
        for cita in self._citas_activas(hoy + timedelta(days=1)).filter(
                recordatorio_1d_enviado_en__isnull=True):
            self._enviar(cita, MensajeWhatsApp.TIPO_CONFIRMACION_1D, 'confirmacion_cita_1_dia',
                lambda d: [d['fecha'], d['hora'], d['sucursal'], d['terapeuta'],
                           d['nombre_paciente'], d['servicio'], d['monto'], d['direccion']])

        # --- Encuesta 1 día después (solo a quien SÍ asistió) ---
        fecha_ayer = hoy - timedelta(days=1)
        citas_ayer = Cita.objects.filter(
            fecha=fecha_ayer,
            estatus=Cita.ESTATUS_SI_ASISTIO,
            encuesta_enviada_en__isnull=True,
        ).exclude(paciente__telefono='').select_related('paciente', 'terapeuta', 'servicio', 'consultorio')

        for cita in citas_ayer:
            self._enviar(cita, MensajeWhatsApp.TIPO_ENCUESTA, 'encuesta_conformidad',
                lambda d: [d['nombre_paciente'], d['servicio'], d['terapeuta']])

        self.stdout.write(self.style.SUCCESS('Recordatorios enviados correctamente.'))

    def _citas_activas(self, fecha):
        return Cita.objects.filter(
            fecha=fecha,
            estatus__in=Cita.ESTATUS_ACTIVOS,
        ).exclude(paciente__telefono='').select_related('paciente', 'terapeuta', 'servicio', 'consultorio')

    def _enviar(self, cita, tipo, nombre_template, get_params):
        datos = wa.construir_parametros_cita(cita)
        parametros = get_params(datos)
        try:
            resp = wa.enviar_template(cita.paciente.telefono, nombre_template, parametros)
            exitoso = 'messages' in resp
        except Exception as e:
            resp = {'error': str(e)}
            exitoso = False

        # Solo se marca cuando Meta aceptó el mensaje; si falló, la cita sigue
        # apareciendo como pendiente en /whatsapp/recordatorios/ para reenviarla
        # a mano en lugar de darse por enviada en silencio.
        if exitoso:
            campo = {
                MensajeWhatsApp.TIPO_RECORDATORIO_5D: 'recordatorio_5d_enviado_en',
                MensajeWhatsApp.TIPO_RECORDATORIO_3D: 'recordatorio_3d_enviado_en',
                MensajeWhatsApp.TIPO_CONFIRMACION_1D: 'recordatorio_1d_enviado_en',
                MensajeWhatsApp.TIPO_ENCUESTA: 'encuesta_enviada_en',
            }[tipo]
            setattr(cita, campo, timezone.now())
            cita.save(update_fields=[campo])

        MensajeWhatsApp.objects.create(
            cita=cita,
            paciente=cita.paciente,
            telefono=cita.paciente.telefono,
            tipo=tipo,
            origen='automatico',
            texto=wa.renderizar_template(nombre_template, parametros),
            exitoso=exitoso,
            respuesta_api=resp,
        )
