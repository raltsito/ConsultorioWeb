"""Motor de puntuación del módulo Instrumentos.

Cada instrumento clínico tiene su propia fórmula para convertir las respuestas
crudas en un puntaje e interpretación. Cada fórmula se registra en `_CALCULADORAS`
identificada por `Instrumento.clave`.

Si no existe una fórmula registrada para un instrumento, el cálculo se omite sin
romper el flujo: las respuestas quedan guardadas para interpretación manual.
"""
from decimal import Decimal, ROUND_HALF_UP


def calcular_resultado_instrumento(envio):
    """Calcula y asigna `puntaje_total`, `interpretacion` y `resultado_detalle`
    sobre un `EnvioInstrumento` ya respondido. No llama save(); quien invoca decide."""
    calculadora = _CALCULADORAS.get(envio.instrumento.clave)
    if calculadora is None:
        return

    respuestas = list(envio.respuestas.select_related('pregunta').order_by('pregunta__orden'))
    resultado = calculadora(respuestas) or {}

    envio.puntaje_total = resultado.get('puntaje_total')
    envio.interpretacion = resultado.get('interpretacion', '')
    envio.resultado_detalle = resultado.get('detalle')


# ── SCID-II ──────────────────────────────────────────────────────────────────

# (trastorno, preguntas_1indexed, umbral_significativo)
_SCID2_TRASTORNOS = [
    ('Evitación',           list(range(1,   8)),  4),
    ('Dependencia',         list(range(8,  16)),  5),
    ('Obsesivo-Compulsivo', list(range(16, 25)),  4),
    ('Pasivo-Agresivo',     list(range(25, 33)),  4),
    ('Depresivo',           list(range(33, 41)),  5),
    ('Paranoide',           list(range(41, 49)),  4),
    ('Esquizotípico',       list(range(49, 60)),  5),
    ('Esquizoide',          list(range(60, 66)),  5),
    ('Histriónico',         list(range(66, 73)),  5),
    ('Narcisista',          list(range(73, 90)),  5),
    ('Límite',              list(range(90, 105)), 5),
    ('Antisocial',          list(range(105, 120)), 5),
]


def _calcular_scid2(respuestas):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    detalle = {}
    significativos = []

    for nombre, preguntas, umbral in _SCID2_TRASTORNOS:
        suma = int(sum(mapa.get(p, Decimal('0')) for p in preguntas))
        es_sig = suma >= umbral
        juicio = 'Significativo' if es_sig else 'No significativo'
        detalle[f'TP {nombre}'] = f'{suma}/{len(preguntas)} — {juicio} (umbral ≥{umbral})'
        if es_sig:
            significativos.append(nombre)

    total = len(significativos)

    if not significativos:
        interpretacion = (
            'No se identificaron trastornos de personalidad clínicamente significativos '
            'en ninguna de las 12 escalas evaluadas.'
        )
    elif total == 1:
        interpretacion = (
            f'Puntuación significativa en: Trastorno de personalidad por {significativos[0]}. '
            'Se recomienda revisión clínica detallada de esta área.'
        )
    else:
        lista = ', '.join(significativos[:-1]) + f' y {significativos[-1]}'
        interpretacion = (
            f'Puntuaciones significativas en {total} escalas: {lista}. '
            'Se recomienda evaluación clínica integral.'
        )

    return {
        'puntaje_total': Decimal(str(total)),
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── SCL-90 ───────────────────────────────────────────────────────────────────

# (subescala, ítems_1indexed, n_ítems, media_normal, ds_normal)
_SCL90_ESCALAS = [
    ('Somatización',               [1,4,12,27,40,42,48,49,52,53,56,58],     12, 0.36, 0.42),
    ('Obsesivo-Compulsivo',        [3,9,10,28,38,45,46,51,55,65],           10, 0.39, 0.45),
    ('Susceptibilidad Interpersonal', [6,21,34,36,37,41,61,69,73],           9, 0.29, 0.39),
    ('Depresión',                  [5,14,15,20,22,26,29,30,31,32,54,71,79], 13, 0.36, 0.44),
    ('Ansiedad',                   [2,17,23,33,39,57,72,78,80,86],          10, 0.30, 0.37),
    ('Hostilidad',                 [11,24,63,67,74,81],                      6, 0.30, 0.40),
    ('Ansiedad Fóbica',            [13,25,47,50,70,75,82],                   7, 0.13, 0.31),
    ('Ideación Paranoide',         [8,18,43,68,76,83],                       6, 0.34, 0.44),
    ('Psicoticismo',               [7,16,35,62,77,84,85,87,88,90],          10, 0.14, 0.25),
]

# ISG: media de los 90 ítems (normativa: M=0.31, DS≈0.32)
_SCL90_ISG_MEDIA = 0.31
_SCL90_ISG_DS    = 0.32


def _calcular_scl90(respuestas):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    detalle = {}
    escalas_elevadas = []

    for nombre, items, n, media_norm, ds_norm in _SCL90_ESCALAS:
        suma = sum(mapa.get(i, Decimal('0')) for i in items)
        media_pac = float(suma) / n
        corte = media_norm + ds_norm

        if media_pac >= corte:
            nivel = 'Elevado'
            escalas_elevadas.append(nombre)
        elif media_pac >= media_norm:
            nivel = 'Leve'
        else:
            nivel = 'Normal'

        media_str = Decimal(str(media_pac)).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        corte_str = Decimal(str(corte)).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        detalle[nombre] = f'Media {media_str} — {nivel} (norm. {media_norm:.2f}, corte {corte_str})'

    # ISG
    suma_total = sum(mapa.get(i, Decimal('0')) for i in range(1, 91))
    isg = float(suma_total) / 90
    isg_nivel = 'Elevado' if isg >= _SCL90_ISG_MEDIA + _SCL90_ISG_DS else (
                'Leve' if isg >= _SCL90_ISG_MEDIA else 'Normal')
    isg_str = Decimal(str(isg)).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
    detalle['ISG (Índice de Severidad Global)'] = (
        f'{isg_str} — {isg_nivel} (norm. {_SCL90_ISG_MEDIA:.2f})'
    )

    # Síntomas positivos (ítems > 0)
    sp = sum(1 for i in range(1, 91) if mapa.get(i, Decimal('0')) > 0)
    detalle['Síntomas Positivos (SP)'] = str(sp)

    # Interpretación
    if isg_nivel == 'Normal' and not escalas_elevadas:
        interpretacion = (
            f'Índice de Severidad Global: {isg_str} (Normal). '
            'No se detectan dimensiones psicopatológicas clínicamente elevadas.'
        )
    else:
        if escalas_elevadas:
            lista = ', '.join(escalas_elevadas)
            interpretacion = (
                f'Índice de Severidad Global: {isg_str} ({isg_nivel}). '
                f'Escalas elevadas (por encima de norma + 1 DS): {lista}. '
                'Se recomienda revisión clínica de las áreas identificadas.'
            )
        else:
            interpretacion = (
                f'Índice de Severidad Global: {isg_str} ({isg_nivel}). '
                'Algunas escalas en nivel leve; ninguna supera el corte clínico.'
            )

    return {
        'puntaje_total': Decimal(str(isg)).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP),
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── Allport — Estudio de Valores ──────────────────────────────────────────────

# Sección 1 (ítems 1-30): (escala_A, escala_B)
# Respuesta almacenada 0-3: A recibe `valor`, B recibe `3 - valor`
_ALLPORT_S1 = {
    1:  ('R', 'S'),  2:  ('T', 'Z'),  3:  ('R', 'T'),  4:  ('S', 'Y'),
    5:  ('T', 'X'),  6:  ('R', 'Z'),  7:  ('S', 'X'),  8:  ('T', 'Y'),
    9:  ('R', 'T'),  10: ('X', 'Z'),  11: ('R', 'Y'),  12: ('S', 'Z'),
    13: ('R', 'X'),  14: ('T', 'S'),  15: ('Y', 'Z'),  16: ('S', 'X'),
    17: ('S', 'Y'),  18: ('X', 'Z'),  19: ('T', 'Y'),  20: ('R', 'S'),
    21: ('T', 'X'),  22: ('R', 'Z'),  23: ('S', 'T'),  24: ('T', 'X'),
    25: ('R', 'S'),  26: ('X', 'Z'),  27: ('R', 'Y'),  28: ('S', 'T'),
    29: ('X', 'Y'),  30: ('T', 'Z'),
}

# Sección 2 (radio_orden 31-94 → escala)
# Cada sub-pregunta aporta directamente su valor (1-4) a la escala
_ALLPORT_S2 = {
    31: 'Z', 32: 'S', 33: 'T', 34: 'R', 35: 'Z', 36: 'R', 37: 'S', 38: 'X',
    39: 'S', 40: 'Z', 41: 'Y', 42: 'T', 43: 'X', 44: 'Y', 45: 'R', 46: 'S',
    47: 'T', 48: 'X', 49: 'Y', 50: 'Z', 51: 'R', 52: 'S', 53: 'Z', 54: 'Y',
    55: 'T', 56: 'Z', 57: 'S', 58: 'X', 59: 'R', 60: 'Y', 61: 'X', 62: 'Z',
    63: 'S', 64: 'T', 65: 'R', 66: 'Y', 67: 'T', 68: 'R', 69: 'X', 70: 'Z',
    71: 'X', 72: 'T', 73: 'Y', 74: 'S', 75: 'Z', 76: 'T', 77: 'R', 78: 'X',
    79: 'S', 80: 'Y', 81: 'S', 82: 'Y', 83: 'Y', 84: 'X', 85: 'Z', 86: 'T',
    87: 'Y', 88: 'X', 89: 'Z', 90: 'T', 91: 'Z', 92: 'S', 93: 'R', 94: 'T',
}

_ALLPORT_NOMBRE = {
    'R': 'Religioso', 'S': 'Social', 'T': 'Teórico',
    'X': 'Económico', 'Y': 'Estético', 'Z': 'Político',
}


def _calcular_allport(respuestas):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    totales = {k: Decimal('0') for k in 'RSTXYZ'}

    # Sección 1
    for orden, (esc_a, esc_b) in _ALLPORT_S1.items():
        v = mapa.get(orden)
        if v is not None:
            totales[esc_a] += v
            totales[esc_b] += Decimal('3') - v

    # Sección 2
    for orden, escala in _ALLPORT_S2.items():
        v = mapa.get(orden)
        if v is not None:
            totales[escala] += v

    ranking = sorted(totales.items(), key=lambda x: -x[1])
    top_escala, top_pts = ranking[0]

    detalle = {
        f'{_ALLPORT_NOMBRE[k]} ({k})': str(int(v))
        for k, v in ranking
    }
    ranking_str = ' > '.join(
        f'{_ALLPORT_NOMBRE[k]}({int(v)})' for k, v in ranking
    )
    interpretacion = (
        f'Valor predominante: {_ALLPORT_NOMBRE[top_escala]} ({top_escala}) '
        f'con {int(top_pts)} puntos. '
        f'Ranking: {ranking_str}.'
    )
    return {
        'puntaje_total': top_pts,
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── Raven SPM ────────────────────────────────────────────────────────────────
# Tabla de percentiles para adultos (18-65 años), normas mexicanas aproximadas.
# Mapea puntaje bruto → percentil más cercano.
_RAVEN_PERCENTILES = {
    0: 1,  1: 1,  2: 1,  3: 1,  4: 2,  5: 2,  6: 3,  7: 3,  8: 4,  9: 5,
    10: 5, 11: 7, 12: 8, 13: 10, 14: 12, 15: 14, 16: 16, 17: 18, 18: 20,
    19: 22, 20: 25, 21: 28, 22: 30, 23: 33, 24: 36, 25: 39, 26: 42,
    27: 45, 28: 48, 29: 51, 30: 54, 31: 57, 32: 60, 33: 63, 34: 66,
    35: 68, 36: 71, 37: 73, 38: 75, 39: 77, 40: 79, 41: 81, 42: 83,
    43: 85, 44: 87, 45: 89, 46: 90, 47: 91, 48: 92, 49: 93, 50: 94,
    51: 95, 52: 96, 53: 97, 54: 97, 55: 98, 56: 98, 57: 99, 58: 99,
    59: 99, 60: 99,
}


def _calcular_raven_nativo(respuestas):
    """Calculadora para el Raven nativo: compara respuesta con la opción marcada correcta."""
    correctas = 0
    for r in respuestas:
        if not r.valor or not r.pregunta.opciones:
            continue
        for opt in r.pregunta.opciones:
            if opt.get('valor') == r.valor and opt.get('correcta'):
                correctas += 1
                break
    return calcular_raven(correctas)


def calcular_raven(puntaje_raw: int) -> dict:
    """Recibe el puntaje bruto (0-60) y devuelve percentil, grado e interpretación.

    Retorna dict con claves: puntaje_total, interpretacion, detalle.
    """
    raw = max(0, min(60, int(puntaje_raw)))
    percentil = _RAVEN_PERCENTILES[raw]

    if percentil >= 95:
        grado, desc = 'I', 'Superior'
    elif percentil >= 75:
        grado, desc = 'II', 'Superior al término medio'
    elif percentil >= 25:
        grado, desc = 'III', 'Término medio'
    elif percentil >= 10:
        grado, desc = 'IV', 'Inferior al término medio'
    else:
        grado, desc = 'V', 'Intelectualmente deficiente'

    interpretacion = (
        f'Puntaje bruto: {raw}/60 — Percentil {percentil} — '
        f'Grado {grado}: {desc}.'
    )
    detalle = {
        'Puntaje bruto': f'{raw} / 60',
        'Percentil': str(percentil),
        'Grado': grado,
        'Clasificación': desc,
    }
    return {
        'puntaje_total': Decimal(str(raw)),
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── Registro de calculadoras ──────────────────────────────────────────────────

_CALCULADORAS = {
    'scid2':   _calcular_scid2,
    'scl90':   _calcular_scl90,
    'allport': _calcular_allport,
    'raven':   _calcular_raven_nativo,
}
