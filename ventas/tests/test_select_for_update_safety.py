import ast
import inspect
import textwrap

from django.test import SimpleTestCase

from clinica.services import incorporar_comision_captacion_a_corte
from ventas.services import (
    _bloquear_borrador,
    _bloquear_y_validar_comisiones,
    crear_borrador_liquidacion,
    registrar_captacion,
)


class SelectForUpdateSafetyTests(SimpleTestCase):
    def assert_bloqueos_sin_select_related(self, funcion):
        arbol = ast.parse(textwrap.dedent(inspect.getsource(funcion)))

        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            metodos = []
            actual = nodo
            while isinstance(actual, ast.Call) and isinstance(actual.func, ast.Attribute):
                metodos.append(actual.func.attr)
                actual = actual.func.value
            self.assertFalse(
                "select_for_update" in metodos and "select_related" in metodos,
                f"{funcion.__name__} combina select_for_update con select_related",
            )

    def test_registrar_captacion_bloquea_sin_relaciones(self):
        self.assert_bloqueos_sin_select_related(registrar_captacion)

    def test_validar_comisiones_bloquea_sin_relaciones(self):
        self.assert_bloqueos_sin_select_related(_bloquear_y_validar_comisiones)

    def test_crear_borrador_bloquea_sin_relaciones(self):
        self.assert_bloqueos_sin_select_related(crear_borrador_liquidacion)

    def test_operar_borrador_bloquea_sin_relaciones(self):
        self.assert_bloqueos_sin_select_related(_bloquear_borrador)

    def test_incorporar_comision_a_nomina_bloquea_sin_relaciones(self):
        self.assert_bloqueos_sin_select_related(
            incorporar_comision_captacion_a_corte
        )
