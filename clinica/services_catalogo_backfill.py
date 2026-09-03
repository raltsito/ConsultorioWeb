from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CategoriaServicio, Servicio


class InventarioCatalogoIncompatible(Exception):
    """El inventario o los datos existentes no coinciden con la matriz curada."""


@dataclass(frozen=True)
class CategoriaEsperada:
    codigo: str
    nombre: str
    orden: int


@dataclass(frozen=True)
class ServicioEsperado:
    id: int
    nombre: str
    codigo: str
    categoria_codigo: str | None
    activo: bool
    reemplazado_por_id: int | None
    modalidad: str | None
    tratamiento_iva: str


@dataclass(frozen=True)
class CambioPrevisto:
    servicio_id: int
    servicio_nombre: str
    campo: str
    valor_actual: object
    valor_esperado: object


@dataclass
class PlanBackfillCatalogo:
    servicios: list
    categorias_por_codigo: dict
    categorias_a_crear: list
    categorias_existentes: list
    cambios: list
    conflictos: list

    @property
    def es_aplicable(self):
        return not self.conflictos


CATEGORIAS_ESPERADAS = (
    CategoriaEsperada('PSICOTERAPIA', 'Psicoterapia', 10),
    CategoriaEsperada('MEDICA', 'Médica', 20),
    CategoriaEsperada('FISIOTERAPIA', 'Fisioterapia', 30),
    CategoriaEsperada('NUTRICION', 'Nutrición', 40),
    CategoriaEsperada('HIPNOSIS', 'Hipnosis', 50),
    CategoriaEsperada('EVALUACION', 'Evaluación', 60),
    CategoriaEsperada('OTROS', 'Otros', 70),
)


_INVENTARIO_BASE = (
    (1, 'Terapia individual', 'PSICO-IND', 'PSICOTERAPIA', True, None, Servicio.MODALIDAD_INDIVIDUAL),
    (2, 'Terapia infantil', 'PSICO-INF', 'PSICOTERAPIA', True, None, None),
    (3, 'Terapia de parejas', 'PSICO-PAR', 'PSICOTERAPIA', True, None, Servicio.MODALIDAD_PAREJA),
    (4, 'Terapia Familiar', 'PSICO-FAM', 'PSICOTERAPIA', True, None, Servicio.MODALIDAD_FAMILIAR),
    (5, 'Evaluacin neuropsicolgica', 'LEGACY-5', 'EVALUACION', False, 16, None),
    (6, 'Consulta psiquitrica', 'LEGACY-6', 'MEDICA', False, 17, None),
    (7, 'Consulta en salud mental', 'MED-SALUD-MENTAL', 'MEDICA', True, None, None),
    (8, 'Consulta nutricional', 'NUTRI-CONS', 'NUTRICION', True, None, None),
    (9, 'Hipnosis', 'HIPNOSIS', 'HIPNOSIS', True, None, None),
    (10, 'Psicotanatologa', 'LEGACY-10', None, False, 18, None),
    (11, 'Consulta Mdica', 'LEGACY-11', 'MEDICA', False, 19, None),
    (12, 'Terapia de Pareja', 'LEGACY-12', 'PSICOTERAPIA', False, 3, Servicio.MODALIDAD_PAREJA),
    (13, 'Terapia Infantil', 'LEGACY-13', 'PSICOTERAPIA', False, 2, None),
    (14, 'Evaluación psicológica infantil', 'EVAL-PSI-INF', 'EVALUACION', True, None, None),
    (15, 'Evaluación psicológica', 'EVAL-PSI', 'EVALUACION', True, None, None),
    (16, 'Evaluación neuropsicológica', 'EVAL-NEURO', 'EVALUACION', True, None, None),
    (17, 'Consulta psiquiátrica', 'MED-PSIQ', 'MEDICA', True, None, None),
    (18, 'Psicotanatología', 'PSICOTAN', None, True, None, None),
    (19, 'Consulta Médica', 'MED-CONS', 'MEDICA', True, None, None),
)


SERVICIOS_ESPERADOS = tuple(
    ServicioEsperado(
        id=servicio_id,
        nombre=nombre,
        codigo=codigo,
        categoria_codigo=categoria_codigo,
        activo=activo,
        reemplazado_por_id=reemplazado_por_id,
        modalidad=modalidad,
        tratamiento_iva=(
            Servicio.IVA_EXENTO
            if servicio_id in {6, 17}
            else Servicio.IVA_INCLUIDO_16
        ),
    )
    for (
        servicio_id,
        nombre,
        codigo,
        categoria_codigo,
        activo,
        reemplazado_por_id,
        modalidad,
    ) in _INVENTARIO_BASE
)


def construir_plan_backfill(*, bloquear=False):
    servicios_queryset = Servicio.objects.order_by('id')
    categorias_queryset = CategoriaServicio.objects.order_by('codigo')
    if bloquear:
        servicios_queryset = servicios_queryset.select_for_update()
        categorias_queryset = categorias_queryset.select_for_update()

    servicios = list(servicios_queryset)
    categorias = list(categorias_queryset)
    conflictos = []

    esperados_por_id = {item.id: item for item in SERVICIOS_ESPERADOS}
    encontrados_por_id = {item.id: item for item in servicios}
    ids_esperados = set(esperados_por_id)
    ids_encontrados = set(encontrados_por_id)

    if ids_encontrados != ids_esperados:
        faltantes = sorted(ids_esperados - ids_encontrados)
        inesperados = sorted(ids_encontrados - ids_esperados)
        conflictos.append(
            'INVENTARIO CAMBIÓ. '
            f'IDs faltantes: {faltantes or "ninguno"}. '
            f'IDs inesperados: {inesperados or "ninguno"}.'
        )

    for servicio_id in sorted(ids_esperados & ids_encontrados):
        actual = encontrados_por_id[servicio_id]
        esperado = esperados_por_id[servicio_id]
        if actual.nombre != esperado.nombre:
            conflictos.append(
                f'ID {servicio_id}: nombre actual {actual.nombre!r}; '
                f'esperado {esperado.nombre!r}.'
            )

    categorias_por_codigo, categorias_a_crear, categorias_existentes = (
        _analizar_categorias(categorias, conflictos)
    )

    cambios = []
    if ids_encontrados == ids_esperados:
        for esperado in SERVICIOS_ESPERADOS:
            _analizar_servicio(
                encontrados_por_id[esperado.id],
                esperado,
                categorias_por_codigo,
                cambios,
                conflictos,
            )

    return PlanBackfillCatalogo(
        servicios=servicios,
        categorias_por_codigo=categorias_por_codigo,
        categorias_a_crear=categorias_a_crear,
        categorias_existentes=categorias_existentes,
        cambios=cambios,
        conflictos=conflictos,
    )


def aplicar_backfill_catalogo():
    with transaction.atomic():
        plan = construir_plan_backfill(bloquear=True)
        _exigir_plan_aplicable(plan)

        categorias_por_codigo = dict(plan.categorias_por_codigo)
        for categoria_esperada in plan.categorias_a_crear:
            categoria = CategoriaServicio.objects.create(
                codigo=categoria_esperada.codigo,
                nombre=categoria_esperada.nombre,
                activo=True,
                orden=categoria_esperada.orden,
            )
            categorias_por_codigo[categoria.codigo] = categoria

        if not plan.cambios and not plan.categorias_a_crear:
            return plan

        servicios_por_id = {servicio.id: servicio for servicio in plan.servicios}
        canonicos = [item for item in SERVICIOS_ESPERADOS if item.activo]
        variantes = [item for item in SERVICIOS_ESPERADOS if not item.activo]

        for esperado in canonicos + variantes:
            servicio = servicios_por_id[esperado.id]
            _asignar_valores_esperados(
                servicio,
                esperado,
                categorias_por_codigo,
                servicios_por_id,
            )
            servicio.full_clean()
            servicio.save(
                update_fields=[
                    'codigo',
                    'categoria',
                    'activo',
                    'reemplazado_por',
                    'modalidad',
                    'tratamiento_iva',
                ]
            )

        verificacion = construir_plan_backfill(bloquear=True)
        _exigir_plan_aplicable(verificacion)
        if verificacion.cambios or verificacion.categorias_a_crear:
            raise InventarioCatalogoIncompatible(
                'La verificación final encontró cambios pendientes; se revirtió todo.'
            )

        return plan


def _analizar_categorias(categorias, conflictos):
    por_codigo = {categoria.codigo: categoria for categoria in categorias}
    por_nombre = {categoria.nombre: categoria for categoria in categorias}
    a_crear = []
    existentes = []

    for esperada in CATEGORIAS_ESPERADAS:
        por_codigo_actual = por_codigo.get(esperada.codigo)
        por_nombre_actual = por_nombre.get(esperada.nombre)

        if por_codigo_actual is None and por_nombre_actual is None:
            a_crear.append(esperada)
            continue

        if por_codigo_actual is None or por_codigo_actual != por_nombre_actual:
            conflictos.append(
                f'Categoría {esperada.codigo}: código o nombre ya está asociado '
                'a una categoría diferente.'
            )
            continue

        if not por_codigo_actual.activo or por_codigo_actual.orden != esperada.orden:
            conflictos.append(
                f'Categoría {esperada.codigo}: activo/orden no coincide con la matriz.'
            )
            continue

        existentes.append(por_codigo_actual)

    return por_codigo, a_crear, existentes


def _analizar_servicio(
    actual,
    esperado,
    categorias_por_codigo,
    cambios,
    conflictos,
):
    _comparar_campo(actual, esperado, 'codigo', (None, ''), cambios, conflictos)
    _comparar_campo(actual, esperado, 'activo', True, cambios, conflictos)
    _comparar_campo(
        actual,
        esperado,
        'reemplazado_por_id',
        None,
        cambios,
        conflictos,
    )
    _comparar_campo(
        actual,
        esperado,
        'modalidad',
        (None, ''),
        cambios,
        conflictos,
    )
    _comparar_campo(
        actual,
        esperado,
        'tratamiento_iva',
        (None, ''),
        cambios,
        conflictos,
    )

    categoria_esperada_id = None
    if esperado.categoria_codigo:
        categoria = categorias_por_codigo.get(esperado.categoria_codigo)
        categoria_esperada_id = categoria.id if categoria else None

    if esperado.categoria_codigo and categoria_esperada_id is None:
        if actual.categoria_id is not None:
            conflictos.append(
                f'ID {actual.id}: categoria actual={actual.categoria_id!r}; '
                f'esperada={esperado.categoria_codigo!r}.'
            )
        else:
            cambios.append(
                CambioPrevisto(
                    actual.id,
                    actual.nombre,
                    'categoria',
                    None,
                    esperado.categoria_codigo,
                )
            )
    else:
        _comparar_valores(
            actual,
            'categoria',
            actual.categoria_id,
            categoria_esperada_id,
            None,
            cambios,
            conflictos,
        )

    if actual.duracion_minutos is not None:
        conflictos.append(
            f'ID {actual.id}: duracion_minutos contiene '
            f'{actual.duracion_minutos!r}; debe revisarse antes del backfill.'
        )
    if actual.orden != 0:
        conflictos.append(
            f'ID {actual.id}: orden contiene {actual.orden!r}; '
            'debe revisarse antes del backfill.'
        )


def _comparar_campo(actual, esperado, campo, vacio_compatible, cambios, conflictos):
    actual_valor = getattr(actual, campo)
    esperado_valor = getattr(esperado, campo)
    _comparar_valores(
        actual,
        campo,
        actual_valor,
        esperado_valor,
        vacio_compatible,
        cambios,
        conflictos,
    )


def _comparar_valores(
    servicio,
    campo,
    actual,
    esperado,
    vacio_compatible,
    cambios,
    conflictos,
):
    if actual == esperado:
        return
    es_vacio_compatible = (
        actual in vacio_compatible
        if isinstance(vacio_compatible, tuple)
        else actual == vacio_compatible
    )
    if es_vacio_compatible:
        cambios.append(
            CambioPrevisto(
                servicio.id,
                servicio.nombre,
                campo,
                actual,
                esperado,
            )
        )
        return
    conflictos.append(
        f'ID {servicio.id}: {campo} actual={actual!r}; esperado={esperado!r}.'
    )


def _asignar_valores_esperados(
    servicio,
    esperado,
    categorias_por_codigo,
    servicios_por_id,
):
    servicio.codigo = esperado.codigo
    servicio.categoria = (
        categorias_por_codigo[esperado.categoria_codigo]
        if esperado.categoria_codigo
        else None
    )
    servicio.activo = esperado.activo
    servicio.reemplazado_por = (
        servicios_por_id[esperado.reemplazado_por_id]
        if esperado.reemplazado_por_id
        else None
    )
    servicio.modalidad = esperado.modalidad
    servicio.tratamiento_iva = esperado.tratamiento_iva


def _exigir_plan_aplicable(plan):
    if plan.conflictos:
        detalle = '\n'.join(f'- {conflicto}' for conflicto in plan.conflictos)
        raise InventarioCatalogoIncompatible(
            'INVENTARIO CAMBIÓ — REQUIERE REVISIÓN DE MATRIZ\n' + detalle
        )
