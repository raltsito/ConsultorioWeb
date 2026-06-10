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
    resultado = calculadora(respuestas, envio=envio) or {}

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


def _calcular_scid2(respuestas, **kwargs):
    mapa_orden = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    # Las escalas de _SCID2_TRASTORNOS están numeradas según los criterios de la
    # hoja de calificación original (1-119), que están desfasados +3 respecto a
    # la numeración del cuestionario (`pregunta.orden`): el criterio r corresponde
    # al ítem (r+3) del cuestionario. Los criterios 117-119 no tienen ítem
    # asociado (la hoja original no los resuelve) y siempre suman 0.
    mapa = {r: mapa_orden.get(r + 3, Decimal('0')) for r in range(1, 117)}
    for r in range(117, 120):
        mapa[r] = Decimal('0')
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

# (subescala, abrev, ítems_1indexed, n_ítems, media_normal, ds_normal)
_SCL90_ESCALAS = [
    ('Somatización',                  'Som.',  [1,4,12,27,40,42,48,49,52,53,56,58],      12, 0.36, 0.42),
    ('Obsesivo-Compulsivo',           'OC',    [3,9,10,28,38,45,46,51,55,65],             10, 0.39, 0.45),
    ('Susceptibilidad Interpersonal', 'S.Int', [6,21,34,36,37,41,61,69,73],               9, 0.29, 0.39),
    ('Depresión',                     'Dep.',  [5,14,15,20,22,26,29,30,31,32,54,71,79],  13, 0.36, 0.44),
    ('Ansiedad',                      'Ans.',  [2,17,23,33,39,57,72,78,80,86],            10, 0.30, 0.37),
    ('Hostilidad',                    'Host.', [11,24,63,67,74,81],                        6, 0.30, 0.40),
    ('Ansiedad Fóbica',               'A.Fob', [13,25,47,50,70,75,82],                    7, 0.13, 0.31),
    ('Ideación Paranoide',            'Par.',  [8,18,43,68,76,83],                         6, 0.34, 0.44),
    ('Psicoticismo',                  'Psic.', [7,16,35,62,77,84,85,87,88,90],            10, 0.14, 0.25),
]

# ISG: media de los 90 ítems (normativa: M=0.31, DS≈0.31)
_SCL90_ISG_MEDIA = 0.31
_SCL90_ISG_DS    = 0.31

# Poblaciones de referencia (medias por subescala en el mismo orden que _SCL90_ESCALAS)
# Fuente: hoja SCL del Excel de calificación del consultorio
_SCL90_REF = {
    'normal':    [0.36, 0.39, 0.29, 0.36, 0.30, 0.30, 0.13, 0.34, 0.14],
    'externos':  [0.99, 1.45, 1.32, 1.74, 1.48, 0.94, 0.96, 1.26, 1.11],
    'internos':  [0.87, 1.47, 1.41, 1.79, 1.47, 1.10, 0.74, 1.16, 0.94],
}
_SCL90_REF_SUMMARY = {
    'normal':   {'isg': 0.31, 'isg_ds': 0.31, 'sp': 19.29, 'mrsp': 1.32, 'mrsp_ds': 0.42},
    'internos': {'isg': 1.30, 'isg_ds': 0.82, 'sp': 50.03, 'mrsp': 2.15, 'mrsp_ds': 0.73},
    'externos': {'isg': 1.26, 'isg_ds': 0.68, 'sp': 50.17, 'mrsp': 2.14, 'mrsp_ds': 0.58},
}


def _calcular_scl90(respuestas, **kwargs):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    detalle = {}
    escalas_elevadas = []
    subescalas_data = []

    for nombre, abrev, items, n, media_norm, ds_norm in _SCL90_ESCALAS:
        suma = sum(mapa.get(i, Decimal('0')) for i in items)
        sp_esc = sum(1 for i in items if mapa.get(i, Decimal('0')) > 0)
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

        subescalas_data.append({
            'nombre': nombre,
            'abrev': abrev,
            'n': n,
            'suma': int(suma),
            'sp': sp_esc,
            'media': round(media_pac, 4),
            'media_norm': media_norm,
            'ds_norm': ds_norm,
            'corte': round(corte, 2),
            'nivel': nivel,
        })

    # ISG
    suma_total = float(sum(mapa.get(i, Decimal('0')) for i in range(1, 91)))
    isg = suma_total / 90
    sp_total = sum(1 for i in range(1, 91) if mapa.get(i, Decimal('0')) > 0)
    mrsp = suma_total / sp_total if sp_total > 0 else 0.0

    isg_nivel = 'Elevado' if isg >= _SCL90_ISG_MEDIA + _SCL90_ISG_DS else (
                'Leve' if isg >= _SCL90_ISG_MEDIA else 'Normal')
    isg_str = Decimal(str(isg)).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
    detalle['ISG (Índice de Severidad Global)'] = (
        f'{isg_str} — {isg_nivel} (norm. {_SCL90_ISG_MEDIA:.2f})'
    )
    detalle['Síntomas Positivos (SP)'] = str(sp_total)
    detalle['MRSP'] = f'{round(mrsp, 2)}'

    # Datos estructurados para tabla y gráfica
    detalle['_scl90_subescalas'] = subescalas_data
    detalle['_scl90_summary'] = {
        'isg':      round(isg, 4),
        'sp_total': sp_total,
        'mrsp':     round(mrsp, 4),
        'isg_nivel': isg_nivel,
        'suma_total': round(suma_total, 1),
    }

    # Interpretación
    if isg_nivel == 'Normal' and not escalas_elevadas:
        interpretacion = (
            f'Índice de Severidad Global: {isg_str} (Normal). '
            'No se detectan dimensiones psicopatológicas clínicamente elevadas.'
        )
    elif escalas_elevadas:
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

# El cuestionario está dividido en "páginas" (Sección 1: 4 páginas de 7-8 ítems;
# Sección 2: 3 páginas de 20 ítems). Cada página tiene su propia rotación
# letra→categoría (diseño tipo cuadrado latino del instrumento original).
_ALLPORT_PAGINAS_S1 = [
    (range(1, 9),   {'R': 'Teórico', 'S': 'Económico', 'T': 'Estético', 'X': 'Social', 'Y': 'Político', 'Z': 'Religioso'}),
    (range(9, 17),  {'Z': 'Teórico', 'Y': 'Económico', 'X': 'Estético', 'T': 'Social', 'S': 'Político', 'R': 'Religioso'}),
    (range(17, 24), {'X': 'Teórico', 'R': 'Económico', 'Z': 'Estético', 'S': 'Social', 'T': 'Político', 'Y': 'Religioso'}),
    (range(24, 31), {'S': 'Teórico', 'X': 'Económico', 'Y': 'Estético', 'R': 'Social', 'Z': 'Político', 'T': 'Religioso'}),
]
_ALLPORT_PAGINAS_S2 = [
    (range(31, 55), {'Y': 'Teórico', 'T': 'Económico', 'S': 'Estético', 'Z': 'Social', 'R': 'Político', 'X': 'Religioso'}),
    (range(55, 75), {'T': 'Teórico', 'Z': 'Económico', 'R': 'Estético', 'Y': 'Social', 'X': 'Político', 'S': 'Religioso'}),
    (range(75, 95), {'R': 'Teórico', 'S': 'Económico', 'T': 'Estético', 'X': 'Social', 'Y': 'Político', 'Z': 'Religioso'}),
]

# Cifras de corrección del baremo original, sumadas al puntaje crudo de cada categoría
_ALLPORT_CORRECCION = {
    'Teórico': 3, 'Económico': -1, 'Estético': 4, 'Social': -3, 'Político': 2, 'Religioso': -5,
}

_ALLPORT_CATEGORIAS = ['Teórico', 'Económico', 'Estético', 'Social', 'Político', 'Religioso']


def _allport_pagina_s1(orden):
    for rango, mapeo in _ALLPORT_PAGINAS_S1:
        if orden in rango:
            return mapeo
    return None


def _allport_pagina_s2(orden):
    for rango, mapeo in _ALLPORT_PAGINAS_S2:
        if orden in rango:
            return mapeo
    return None


def _calcular_allport(respuestas, **kwargs):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    crudo = {c: Decimal('0') for c in _ALLPORT_CATEGORIAS}
    sec1 = {c: Decimal('0') for c in _ALLPORT_CATEGORIAS}
    sec2 = {c: Decimal('0') for c in _ALLPORT_CATEGORIAS}

    # Sección 1
    for orden, (esc_a, esc_b) in _ALLPORT_S1.items():
        v = mapa.get(orden)
        if v is None:
            continue
        mapeo = _allport_pagina_s1(orden)
        cat_a, cat_b = mapeo[esc_a], mapeo[esc_b]
        crudo[cat_a] += v
        crudo[cat_b] += Decimal('3') - v
        sec1[cat_a] += v
        sec1[cat_b] += Decimal('3') - v

    # Sección 2
    for orden, escala in _ALLPORT_S2.items():
        v = mapa.get(orden)
        if v is None:
            continue
        mapeo = _allport_pagina_s2(orden)
        cat = mapeo[escala]
        crudo[cat] += v
        sec2[cat] += v

    # Cifras de corrección + totales finales
    finales = {c: crudo[c] + Decimal(str(_ALLPORT_CORRECCION[c])) for c in _ALLPORT_CATEGORIAS}

    ranking = sorted(finales.items(), key=lambda x: -x[1])
    top_cat, top_pts = ranking[0]

    detalle = {}
    for cat, final in ranking:
        bruto = crudo[cat]
        corr = _ALLPORT_CORRECCION[cat]
        signo = '+' if corr >= 0 else ''
        detalle[cat] = f'{int(bruto)} {signo}{corr} = {int(final)}'

    for cat, v in sorted(sec1.items(), key=lambda x: -x[1]):
        detalle[f'Sec.1 — {cat}'] = str(int(v))
    for cat, v in sorted(sec2.items(), key=lambda x: -x[1]):
        detalle[f'Sec.2 — {cat}'] = str(int(v))

    ranking_str = ' > '.join(f'{cat}({int(v)})' for cat, v in ranking)
    interpretacion = (
        f'Valor predominante: {top_cat} con {int(top_pts)} puntos (tras corrección). '
        f'Ranking: {ranking_str}.'
    )
    return {
        'puntaje_total': top_pts,
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── Raven SPM ────────────────────────────────────────────────────────────────

# Puntajes esperados por serie (A,B,C,D,E) dado el puntaje total.
# Fuente: hoja RAVEN del Excel de calificación del consultorio.
_RAVEN_ESPERADOS = {
    15: (8, 4, 2, 1, 0),  16: (8, 4, 3, 1, 0),  17: (8, 5, 3, 1, 0),
    18: (8, 5, 3, 2, 0),  19: (8, 6, 3, 2, 0),  20: (8, 6, 3, 2, 1),
    21: (8, 6, 4, 2, 1),  22: (9, 6, 4, 2, 1),  23: (9, 7, 4, 2, 1),
    24: (9, 7, 4, 3, 1),  25: (10, 7, 4, 3, 1), 26: (10, 7, 5, 3, 1),
    27: (10, 7, 5, 4, 1), 28: (10, 7, 6, 4, 1), 29: (10, 7, 6, 5, 1),
    30: (10, 7, 6, 5, 2), 31: (10, 7, 7, 5, 2), 32: (10, 8, 7, 5, 2),
    33: (11, 8, 7, 5, 2), 34: (11, 8, 7, 6, 2), 35: (11, 8, 7, 7, 2),
    36: (11, 8, 8, 7, 2), 37: (11, 9, 8, 7, 2), 38: (11, 9, 8, 8, 2),
    39: (11, 9, 8, 8, 3), 40: (11, 10, 8, 8, 3), 41: (11, 10, 9, 8, 3),
    42: (11, 10, 9, 9, 3), 43: (12, 10, 9, 9, 3), 44: (12, 10, 9, 9, 4),
    45: (12, 10, 9, 9, 5), 46: (12, 10, 10, 9, 5), 47: (12, 10, 10, 9, 6),
    48: (12, 11, 10, 9, 6), 49: (12, 11, 10, 10, 6), 50: (12, 11, 10, 10, 7),
    51: (12, 11, 11, 10, 7), 52: (12, 11, 11, 10, 8), 53: (12, 11, 11, 11, 8),
    54: (12, 12, 11, 11, 8), 55: (12, 12, 11, 11, 9), 56: (12, 12, 12, 11, 9),
    57: (12, 12, 12, 11, 10), 58: (12, 12, 12, 12, 10), 59: (12, 12, 12, 12, 11),
    60: (12, 12, 12, 12, 12),
}

# Normas por edad del Raven SPM extraídas de la hoja RAVEN del Excel.
# Formato: {edad: [(percentil_piso, puntaje_minimo), ...]} de mayor a menor.
# Para edades fuera del rango [13, 25] se usa el extremo más cercano.
_RAVEN_NORMAS_EDAD = {
    13: [(99,59),(95,56),(90,55),(75,52),(50,48),(25,44),(10,39),(5,36)],
    14: [(99,59),(95,58),(90,55),(75,54),(50,51),(25,47),(10,43),(5,38)],
    15: [(99,59),(95,56),(90,55),(75,52),(50,49),(25,44),(10,40),(5,36)],
    16: [(99,59),(95,58),(90,55),(75,54),(50,51),(25,48),(10,43),(5,39)],
    17: [(99,58),(95,58),(90,57),(75,54),(50,51),(25,48),(10,45),(5,42)],
    18: [(99,58),(95,57),(90,56),(75,55),(50,53),(25,49),(10,44),(5,42)],
    19: [(99,59),(95,57),(90,56),(75,54),(50,52),(25,48),(10,46),(5,43)],
    20: [(99,59),(95,57),(90,56),(75,54),(50,52),(25,48),(10,46),(5,43)],
    21: [(99,59),(95,58),(90,57),(75,54),(50,51),(25,48),(10,45),(5,42)],
    22: [(99,59),(95,58),(90,57),(75,54),(50,51),(25,48),(10,45),(5,42)],
    23: [(99,60),(95,59),(90,58),(75,55),(50,53),(25,49),(10,44),(5,42)],
    24: [(99,60),(95,59),(90,58),(75,55),(50,53),(25,49),(10,44),(5,42)],
    25: [(99,59),(95,58),(90,57),(75,55),(50,50),(25,45),(10,42),(5,39)],
}


def _raven_percentil_edad(raw, edad):
    """Devuelve el percentil para un puntaje dado y edad, usando la tabla de normas por edad."""
    edad_clamped = max(13, min(25, int(edad)))
    for percentil, minimo in _RAVEN_NORMAS_EDAD[edad_clamped]:
        if raw >= minimo:
            return percentil
    return 1  # por debajo del P5


_RAVEN_SERIES = [('A', 1, 12), ('B', 13, 24), ('C', 25, 36), ('D', 37, 48), ('E', 49, 60)]


def _calcular_raven_nativo(respuestas, envio=None, **kwargs):
    """Calculadora para el Raven nativo: compara respuesta con la opción marcada correcta."""
    series_cnt = {s: 0 for s, _, _ in _RAVEN_SERIES}
    total = 0
    for r in respuestas:
        if not r.valor or not r.pregunta.opciones:
            continue
        for opt in r.pregunta.opciones:
            if opt.get('valor') == r.valor and opt.get('correcta'):
                for serie, start, end in _RAVEN_SERIES:
                    if start <= r.pregunta.orden <= end:
                        series_cnt[serie] += 1
                        break
                total += 1
                break

    # Determinar edad del paciente para usar normas correctas por edad
    edad = None
    if envio is not None:
        try:
            from datetime import date
            fn = envio.paciente.fecha_nacimiento
            hoy = date.today()
            edad = (hoy - fn).days // 365
        except Exception:
            edad = None

    resultado = calcular_raven(total, edad=edad)

    # Puntajes por serie
    series_detalle = {
        f'Serie {s} (ítems {start}–{end})': f'{series_cnt[s]}/12'
        for s, start, end in _RAVEN_SERIES
    }

    # Análisis de discrepancia: actual vs esperado por serie
    esperados = _RAVEN_ESPERADOS.get(total)
    disc_detalle = {}
    alertas = []
    if esperados:
        for (serie, _, _), esp in zip(_RAVEN_SERIES, esperados):
            real = series_cnt[serie]
            diff = real - esp
            if abs(diff) >= 3:
                nivel = 'Significativa'
                alertas.append(f'Serie {serie} ({diff:+d})')
            elif abs(diff) == 2:
                nivel = 'Notable'
                alertas.append(f'Serie {serie} ({diff:+d})')
            else:
                nivel = 'Normal'
            signo = f'{diff:+d}' if diff != 0 else '0'
            disc_detalle[f'Disc. Serie {serie}'] = f'real {real} · esp {esp} · dif {signo} — {nivel}'

    if esperados:
        patron = 'Inconsistente: ' + ', '.join(alertas) if alertas else 'Consistente'
    else:
        patron = 'Sin datos normativos (puntaje total fuera del rango de la tabla)'
    disc_detalle['Patrón de respuesta'] = patron

    resultado['detalle'] = {**series_detalle, **disc_detalle, **resultado['detalle']}
    resultado['discrepancia'] = {
        'esperados': {s: e for (s, _, _), e in zip(_RAVEN_SERIES, esperados)} if esperados else {},
        'reales': dict(series_cnt),
        'alertas': alertas,
        'patron': patron,
    }
    return resultado


def calcular_raven(puntaje_raw: int, edad: int = None) -> dict:
    """Recibe el puntaje bruto (0-60) y la edad del evaluado; devuelve percentil,
    grado e interpretación usando la tabla de normas por edad.

    Si edad es None se usa 25 (norma adulto máxima disponible).
    Retorna dict con claves: puntaje_total, interpretacion, detalle.
    """
    raw = max(0, min(60, int(puntaje_raw)))
    edad_efectiva = int(edad) if edad is not None else 25
    percentil = _raven_percentil_edad(raw, edad_efectiva)

    if percentil >= 95:
        grado, desc = 'I', 'Superior'
    elif percentil >= 75:
        grado, desc = 'II', 'Superior al término medio'
    elif percentil >= 25:
        grado, desc = 'III', 'Término medio'
    elif percentil >= 10:
        grado, desc = 'IV', 'Inferior al término medio'
    else:
        grado, desc = 'V', 'Deficiente'

    interpretacion = (
        f'Puntaje bruto: {raw}/60 — Percentil {percentil} (edad {edad_efectiva} años) — '
        f'Grado {grado}: {desc}.'
    )
    detalle = {
        'Puntaje bruto': f'{raw} / 60',
        'Edad utilizada': str(edad_efectiva),
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
