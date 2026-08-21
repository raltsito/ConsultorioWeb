from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User

from .models import (
    Cita,
    Consultorio,
    Division,
    Horario,
    Paciente,
    ReglaTerapeuta,
    Servicio,
    TabuladorGeneral,
    Terapeuta,
)


class ClinicaTestDataMixin:
    """Datos sintéticos mínimos compartidos por las pruebas de caracterización."""

    fecha = date(2030, 1, 7)  # lunes
    hora = time(10, 0)

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="staff_pruebas",
            password="pruebas",
            is_staff=True,
            is_superuser=True,
        )
        cls.usuario_terapeuta = User.objects.create_user(
            username="terapeuta_pruebas", password="pruebas"
        )
        cls.usuario_otro_terapeuta = User.objects.create_user(
            username="otro_terapeuta_pruebas", password="pruebas"
        )
        cls.terapeuta = Terapeuta.objects.create(
            usuario=cls.usuario_terapeuta, nombre="Terapeuta Uno"
        )
        cls.otro_terapeuta = Terapeuta.objects.create(
            usuario=cls.usuario_otro_terapeuta, nombre="Terapeuta Dos"
        )
        cls.division = Division.objects.create(nombre="División Pruebas")
        cls.consultorio = Consultorio.objects.create(
            nombre="Consultorio Uno", sede="republica", activo=True
        )
        cls.otro_consultorio = Consultorio.objects.create(
            nombre="Consultorio Dos", sede="republica", activo=True
        )
        cls.servicio = Servicio.objects.create(
            nombre="Terapia de prueba", precio=Decimal("600.00")
        )
        cls.otro_servicio = Servicio.objects.create(
            nombre="Otro servicio", precio=Decimal("900.00")
        )
        cls.paciente = Paciente.objects.create(
            nombre="Paciente Prueba",
            fecha_nacimiento=date(1990, 1, 1),
            sexo="Femenino",
            telefono="5550000001",
            servicio_inicial=cls.servicio,
            division=cls.division,
        )
        cls.otro_paciente = Paciente.objects.create(
            nombre="Paciente Adicional",
            fecha_nacimiento=date(1991, 2, 2),
            sexo="Masculino",
            telefono="5550000002",
            servicio_inicial=cls.servicio,
            division=cls.division,
        )
        for terapeuta in (cls.terapeuta, cls.otro_terapeuta):
            Horario.objects.create(
                terapeuta=terapeuta,
                dia=0,
                hora_inicio=time(8, 0),
                hora_fin=time(18, 0),
                sede="republica",
            )

    def crear_cita(self, **overrides):
        datos = {
            "paciente": self.paciente,
            "fecha": self.fecha,
            "hora": self.hora,
            "tipo_paciente": Cita.TIPO_SEGUIMIENTO,
            "division": self.division,
            "consultorio": self.consultorio,
            "servicio": self.servicio,
            "terapeuta": self.terapeuta,
            "costo": Decimal("500.00"),
            "estatus": Cita.ESTATUS_CONFIRMADA,
            "tiene_descuento": False,
        }
        datos.update(overrides)
        return Cita.objects.create(**datos)

    def crear_regla(self, terapeuta=None, **overrides):
        datos = {
            "terapeuta": terapeuta or self.terapeuta,
            "pago_por_sesion": Decimal("250.00"),
        }
        datos.update(overrides)
        return ReglaTerapeuta.objects.create(**datos)

    def crear_tabulador(self, numero=1, **overrides):
        datos = {
            "numero": numero,
            "descripcion": "Categoría de prueba",
            "pago_base": Decimal("200.00"),
        }
        datos.update(overrides)
        return TabuladorGeneral.objects.create(**datos)
