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


# ── DASS-21 ───────────────────────────────────────────────────────────────────

# (subescala, items, [(límite_superior, nivel), ...]) — cortes del Excel DASS-21
# (hoja 'DASS-21'); si supera el último corte el nivel es 'Extremadamente severa'.
_DASS21_SUBESCALAS = [
    ('Depresión', [3, 5, 10, 13, 16, 17, 21],
     [(4, 'Normal'), (6, 'Leve'), (10, 'Moderada'), (13, 'Severa')]),
    ('Ansiedad', [2, 4, 7, 9, 15, 19, 20],
     [(3, 'Normal'), (4, 'Leve'), (7, 'Moderada'), (9, 'Severa')]),
    ('Estrés', [1, 6, 8, 11, 12, 14, 18],
     [(7, 'Normal'), (9, 'Leve'), (12, 'Moderada'), (16, 'Severa')]),
]


def _calcular_dass21(respuestas, **kwargs):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    detalle = {}
    resumen = []
    elevadas = []
    total = Decimal('0')

    for nombre, items, cortes in _DASS21_SUBESCALAS:
        suma = sum(mapa.get(i, Decimal('0')) for i in items)
        nivel = 'Extremadamente severa'
        for limite, n in cortes:
            if suma <= limite:
                nivel = n
                break
        total += suma
        detalle[nombre] = f'{suma} / 21 — {nivel}'
        resumen.append(f'{nombre}: {suma} ({nivel})')
        if nivel != 'Normal':
            elevadas.append(nombre)

    if elevadas:
        cierre = f'Subescalas por encima del rango normal: {", ".join(elevadas)}.'
    else:
        cierre = 'Las tres subescalas se encuentran en rango normal.'
    return {
        'puntaje_total': total,
        'interpretacion': ' · '.join(resumen) + f'. {cierre}',
        'detalle': detalle,
    }


# ── TDS (Trastornos del Sueño) ────────────────────────────────────────────────

# Factores e ítems según los encabezados de cálculo del Excel TDS (el ítem 8 no
# pertenece a ningún factor, así está definido en el instrumento original).
_TDS_FACTORES = [
    ('Somnolencia excesiva diurna', [1, 2, 3, 4, 5]),
    ('Insomnio inicial', [10, 11, 12]),
    ('Insomnio intermedio', [9, 13]),
    ('Insomnio terminal', [6, 7]),
    ('Apnea obstructiva', [14, 15, 16]),
    ('Parálisis del dormir', [17, 30]),
    ('Enuresis', [18]),
    ('Bruxismo', [19]),
    ('Sonambulismo', [20, 21]),
    ('Somniloquio', [22]),
    ('Ronquido', [23, 24]),
    ('Piernas inquietas', [25, 26]),
    ('Pesadillas', [27]),
    ('Uso de medicamentos hipnóticos', [28]),
    ('Uso de medicamentos estimulantes', [29]),
]


def _tds_nivel(proporcion):
    if proporcion == 0:
        return 'Nulo'
    if proporcion <= 0.25:
        return 'Bajo'
    if proporcion <= 0.5:
        return 'Medio'
    if proporcion <= 0.75:
        return 'Alto'
    return 'Muy alto'


def _calcular_tds(respuestas, **kwargs):
    mapa = {r.pregunta.orden: (r.valor_numerico or Decimal('0')) for r in respuestas}
    detalle = {}
    conteo = {'Nulo': 0, 'Bajo': 0, 'Medio': 0, 'Alto': 0, 'Muy alto': 0}
    destacados = []

    for nombre, items in _TDS_FACTORES:
        maximo = 4 * len(items)
        suma = sum(mapa.get(i, Decimal('0')) for i in items)
        nivel = _tds_nivel(float(suma) / maximo)
        conteo[nivel] += 1
        detalle[nombre] = f'{suma} / {maximo} — {nivel}'
        if nivel in ('Alto', 'Muy alto'):
            destacados.append(f'{nombre} ({nivel.lower()})')

    positivos = sum(n for nivel, n in conteo.items() if nivel != 'Nulo')
    detalle['Factores positivos'] = (
        f'{positivos} de {len(_TDS_FACTORES)} '
        f'(bajo: {conteo["Bajo"]}, medio: {conteo["Medio"]}, '
        f'alto: {conteo["Alto"]}, muy alto: {conteo["Muy alto"]})'
    )

    if destacados:
        interpretacion = (
            f'{positivos} factores de alteración del sueño positivos. '
            f'En nivel alto o muy alto: {", ".join(destacados)}.'
        )
    elif positivos:
        interpretacion = (
            f'{positivos} factores de alteración del sueño positivos, '
            'todos en nivel bajo o medio.'
        )
    else:
        interpretacion = 'Sin factores de alteración del sueño positivos.'

    total = sum(mapa.get(i, Decimal('0')) for i in range(1, 31))
    return {'puntaje_total': total, 'interpretacion': interpretacion, 'detalle': detalle}


# ── TCI (Registro de Opiniones — ideas autolimitadoras) ──────────────────────

# Cada idea se mide con los ítems k, k+10, ..., k+90. Los ítems 'invertidos'
# puntúan al responder NO. Clave de corrección deducida y verificada contra las
# 314 aplicaciones resueltas del Excel TCI (hoja DTCI, columnas Cálculos 1-10).
_TCI_IDEAS = [
    ('Necesidad de aprobación de los demás', [31, 41, 61, 91]),
    ('Perfeccionismo y autoexigencia', [22, 32, 52, 92]),
    ('Condena de los demás por sus errores', [43, 83, 93]),
    ('Catastrofismo ante la frustración', [4, 14, 44, 54, 64, 74, 94]),
    ('Atribución externa del malestar', [5, 15, 25, 35, 45, 65, 85, 95]),
    ('Ansiedad ante lo desconocido o incierto', [16, 36, 56, 86]),
    ('Evitación de problemas y responsabilidades', [17, 37, 57, 77, 87, 97]),
    ('Dependencia de algo más fuerte que uno mismo', [48, 58, 68, 88, 98]),
    ('Influencia determinante del pasado', [29, 39, 59, 99]),
    ('Felicidad por inactividad y ocio indefinido', [20, 30, 40, 60]),
]


def _calcular_tci(respuestas, **kwargs):
    mapa = {r.pregunta.orden: int(r.valor_numerico or 0) for r in respuestas}
    detalle = {}
    limitantes = []
    total = 0

    for k, (nombre, invertidos) in enumerate(_TCI_IDEAS, start=1):
        items = [k + 10 * j for j in range(10)]
        suma = sum(1 - mapa.get(i, 0) if i in invertidos else mapa.get(i, 0)
                   for i in items)
        if suma >= 7:
            nivel = 'Limitante en muchas áreas de su vida'
        elif suma >= 5:
            nivel = 'Limitante en determinadas circunstancias'
        else:
            nivel = 'No significativa'
        total += suma
        detalle[f'Idea {k}: {nombre}'] = f'{suma} / 10 — {nivel}'
        if suma >= 5:
            limitantes.append(f'{nombre.lower()} ({suma})')

    if limitantes:
        interpretacion = (
            'Ideas autolimitadoras con puntuación significativa (≥5): '
            f'{", ".join(limitantes)}.'
        )
    else:
        interpretacion = (
            'Ninguna idea autolimitadora alcanza puntuación significativa (≥5).'
        )
    return {
        'puntaje_total': Decimal(total),
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── ISRA (Inventario de Situaciones y Respuestas de Ansiedad) ────────────────

# Estructura del cuestionario aplicado (251 reactivos en el orden del Excel):
#   1-64    respuestas cognitivas (C)
#   65-187  respuestas fisiológicas (F) — la PD fisiológica es la suma / 2
#   188-251 respuestas motoras (M)
# Las áreas situacionales F1-F4 suman los reactivos crudos de sus situaciones.
# Mapeos y baremos extraídos de las fórmulas del Excel ISRA (hojas RESPUESTAS y
# BAREMOS) y validados contra el caso resuelto de la hoja ISRA.

_ISRA_BLOQUES = {'C': (1, 64), 'F': (65, 187), 'M': (188, 251)}

_ISRA_AREAS = {
    'Evaluación':    {1, 4, 8, 10, 11, 13},
    'Interpersonal': {7, 15, 18},
    'Fóbica':        {12, 14, 17, 19},
    'Cotidiana':     {5, 21, 22},
}

# Situación (1-23) por número de reactivo. Los reactivos 57, 177 y 244 no
# participan en las áreas F1-F4 (así están definidos en el Excel).
_ISRA_SITUACION_POR_ORDEN = {
    1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5, 10: 6,
    11: 6, 12: 6, 13: 6, 14: 7, 15: 8, 16: 8, 17: 9, 18: 9, 19: 10, 20: 10,
    21: 10, 22: 10, 23: 11, 24: 12, 25: 12, 26: 12, 27: 13, 28: 13, 29: 13, 30: 13,
    31: 14, 32: 15, 33: 16, 34: 17, 35: 17, 36: 17, 37: 17, 38: 17, 39: 18, 40: 18,
    41: 19, 42: 19, 43: 19, 44: 19, 45: 19, 46: 20, 47: 20, 48: 20, 49: 21, 50: 21,
    51: 21, 52: 21, 53: 21, 54: 22, 55: 22, 56: 22, 58: 23, 59: 23, 60: 23,
    61: 23, 62: 23, 63: 23, 64: 23, 65: 1, 66: 1, 67: 1, 68: 1, 69: 1, 70: 1,
    71: 1, 72: 2, 73: 2, 74: 2, 75: 2, 76: 2, 77: 2, 78: 2, 79: 3, 80: 3,
    81: 3, 82: 3, 83: 3, 84: 3, 85: 3, 86: 3, 87: 4, 88: 5, 89: 5, 90: 5,
    91: 5, 92: 6, 93: 6, 94: 6, 95: 6, 96: 7, 97: 7, 98: 7, 99: 7, 100: 7,
    101: 8, 102: 8, 103: 8, 104: 8, 105: 8, 106: 8, 107: 8, 108: 9, 109: 9, 110: 9,
    111: 9, 112: 10, 113: 10, 114: 10, 115: 10, 116: 10, 117: 10, 118: 10, 119: 10, 120: 11,
    121: 11, 122: 11, 123: 11, 124: 12, 125: 12, 126: 12, 127: 12, 128: 12, 129: 12, 130: 12,
    131: 13, 132: 13, 133: 13, 134: 13, 135: 13, 136: 14, 137: 14, 138: 14, 139: 15, 140: 15,
    141: 15, 142: 15, 143: 16, 144: 16, 145: 16, 146: 16, 147: 16, 148: 16, 149: 17, 150: 17,
    151: 17, 152: 17, 153: 17, 154: 18, 155: 18, 156: 18, 157: 18, 158: 18, 159: 19, 160: 19,
    161: 19, 162: 19, 163: 19, 164: 19, 165: 20, 166: 20, 167: 20, 168: 20, 169: 21, 170: 21,
    171: 21, 172: 21, 173: 21, 174: 21, 175: 21, 176: 22, 178: 23, 179: 23, 180: 23,
    181: 23, 182: 23, 183: 23, 184: 23, 185: 23, 186: 23, 187: 23, 188: 1, 189: 1, 190: 1,
    191: 2, 192: 2, 193: 3, 194: 3, 195: 3, 196: 3, 197: 3, 198: 3, 199: 4, 200: 4,
    201: 4, 202: 5, 203: 5, 204: 5, 205: 6, 206: 6, 207: 7, 208: 8, 209: 8, 210: 8,
    211: 9, 212: 9, 213: 9, 214: 10, 215: 11, 216: 11, 217: 11, 218: 12, 219: 12, 220: 12,
    221: 12, 222: 13, 223: 13, 224: 14, 225: 14, 226: 15, 227: 16, 228: 16, 229: 17, 230: 17,
    231: 17, 232: 17, 233: 17, 234: 18, 235: 18, 236: 18, 237: 18, 238: 18, 239: 19, 240: 20,
    241: 20, 242: 21, 243: 22, 245: 23, 246: 23, 247: 23, 248: 23, 249: 23, 250: 23,
    251: 23,
}

_INF = float('inf')

# (sexo, escala) -> [(lo_exclusivo, hi_exclusivo, percentil), ...]
_ISRA_BAREMOS = {
    ('Hombre', 'Cognitiva'): [(-_INF, 23.0, 5), (22.0, 29.0, 10), (28.0, 35.0, 15), (34.0, 38.0, 20), (37.0, 42.0, 25), (41.0, 44.0, 30), (43.0, 47.0, 35), (46.0, 52.0, 40), (51.0, 55.0, 45), (54.0, 60.0, 50), (59.0, 67.0, 55), (66.0, 71.0, 60), (70.0, 76.0, 65), (75.0, 80.0, 70), (79.0, 85.0, 75), (84.0, 91.0, 80), (90.0, 96.0, 85), (95.0, 109.0, 90), (108.0, 124.0, 95), (123.0, _INF, 99)],
    ('Hombre', 'Cotidiana'): [(-0.5, 0.5, 5), (0.5, 1.5, 10), (1.5, 2.5, 20), (2.5, 3.5, 30), (3.5, 4.5, 35), (4.5, 5.5, 40), (5.5, 6.5, 45), (6.5, 7.5, 50), (7.5, 8.5, 55), (8.5, 9.5, 60), (9.0, 12.0, 65), (11.0, 13.0, 70), (12.0, 15.0, 75), (14.0, 18.0, 80), (17.0, 25.0, 85), (24.0, 35.0, 90), (34.0, 42.0, 95), (41.0, _INF, 99)],
    ('Hombre', 'Evaluación'): [(-_INF, 22.0, 5), (21.0, 28.0, 10), (27.0, 31.0, 15), (30.0, 33.0, 20), (32.0, 38.0, 25), (37.0, 45.0, 30), (44.0, 49.0, 35), (48.0, 53.0, 40), (52.0, 58.0, 45), (57.0, 64.0, 50), (63.0, 67.0, 55), (66.0, 72.0, 60), (71.0, 77.0, 65), (76.0, 82.0, 70), (81.0, 88.0, 75), (87.0, 92.0, 80), (91.0, 99.0, 85), (98.0, 108.0, 90), (107.0, 137.0, 95), (136.0, _INF, 99)],
    ('Hombre', 'Fisiológica'): [(-_INF, 7.0, 5), (6.0, 9.0, 10), (8.0, 11.0, 15), (10.0, 15.0, 20), (14.0, 16.0, 25), (15.0, 19.0, 30), (18.0, 20.0, 35), (19.0, 23.0, 40), (22.0, 26.0, 45), (25.0, 29.0, 50), (28.0, 30.0, 55), (29.0, 32.0, 60), (31.0, 36.0, 65), (35.0, 40.0, 70), (39.0, 45.0, 75), (44.0, 48.0, 80), (47.0, 53.0, 85), (52.0, 68.0, 90), (67.0, 84.0, 95), (83.0, _INF, 99)],
    ('Hombre', 'Fóbica'): [(-_INF, 3.0, 5), (2.0, 5.0, 10), (4.0, 8.0, 15), (7.0, 10.0, 20), (9.0, 14.0, 25), (13.0, 17.0, 30), (16.0, 19.0, 35), (18.0, 21.0, 40), (20.0, 23.0, 45), (22.0, 25.0, 50), (24.0, 28.0, 55), (27.0, 34.0, 60), (33.0, 37.0, 65), (36.0, 41.0, 70), (40.0, 45.0, 75), (44.0, 50.0, 80), (49.0, 60.0, 85), (59.0, 71.0, 90), (70.0, 90.0, 95), (89.0, _INF, 99)],
    ('Hombre', 'Interpersonal'): [(-_INF, 3.0, 5), (2.0, 4.0, 10), (3.0, 6.0, 15), (5.0, 7.0, 20), (6.0, 8.0, 25), (7.0, 9.0, 30), (8.0, 10.0, 35), (9.0, 12.0, 40), (11.0, 13.0, 45), (12.0, 14.0, 50), (13.0, 16.0, 55), (15.0, 17.0, 60), (16.0, 19.0, 65), (18.0, 21.0, 70), (20.0, 23.0, 75), (22.0, 25.0, 80), (24.0, 28.0, 85), (27.0, 34.0, 90), (33.0, 45.0, 95), (44.0, _INF, 99)],
    ('Hombre', 'Motora'): [(-_INF, 7.0, 5), (6.0, 12.0, 10), (11.0, 16.0, 15), (15.0, 20.0, 20), (19.0, 22.0, 25), (21.0, 24.0, 30), (23.0, 27.0, 35), (26.0, 29.0, 40), (28.0, 31.0, 45), (30.0, 35.0, 50), (34.0, 41.0, 55), (40.0, 46.0, 60), (45.0, 51.0, 65), (50.0, 59.0, 70), (58.0, 63.0, 75), (62.0, 69.0, 80), (68.0, 80.0, 85), (79.0, 94.0, 90), (93.0, 108.0, 95), (107.0, _INF, 99)],
    ('Hombre', 'Total'): [(-_INF, 55.0, 5), (54.0, 64.0, 10), (63.0, 67.0, 15), (66.0, 73.0, 20), (72.0, 83.0, 25), (82.0, 88.0, 30), (87.0, 97.0, 35), (96.0, 106.0, 40), (105.0, 115.0, 45), (114.0, 129.0, 50), (128.0, 140.0, 55), (139.0, 152.0, 60), (151.0, 165.0, 65), (164.0, 176.0, 70), (175.0, 186.0, 75), (185.0, 197.0, 80), (196.0, 211.0, 85), (210.0, 260.0, 90), (259.0, 296.0, 95), (295.0, _INF, 99)],
    ('Mujer', 'Cognitiva'): [(-_INF, 33.0, 5), (32.0, 37.0, 10), (36.0, 40.0, 15), (39.0, 44.0, 20), (43.0, 48.0, 25), (47.0, 52.0, 30), (51.0, 55.0, 35), (54.0, 59.0, 40), (58.0, 64.0, 45), (63.0, 67.0, 50), (66.0, 73.0, 55), (72.0, 78.0, 60), (77.0, 84.0, 65), (83.0, 90.0, 70), (89.0, 94.0, 75), (93.0, 102.0, 80), (101.0, 117.0, 85), (116.0, 129.0, 90), (128.0, 164.0, 95), (163.0, _INF, 99)],
    ('Mujer', 'Cotidiana'): [(-_INF, 2.0, 5), (1.5, 2.5, 10), (2.5, 3.5, 15), (3.5, 4.5, 25), (4.5, 5.5, 30), (5.5, 6.5, 35), (6.5, 7.5, 40), (7.0, 10.0, 45), (9.5, 10.5, 50), (10.0, 13.0, 55), (12.5, 13.5, 60), (13.0, 17.0, 65), (16.0, 19.0, 70), (18.0, 21.0, 75), (20.0, 24.0, 80), (23.0, 31.0, 85), (30.0, 41.0, 90), (40.0, 58.0, 95), (57.0, _INF, 99)],
    ('Mujer', 'Evaluación'): [(-_INF, 31.0, 5), (30.0, 36.0, 10), (35.0, 40.0, 15), (39.0, 44.0, 20), (43.0, 49.0, 25), (48.0, 53.0, 30), (52.0, 57.0, 35), (56.0, 60.0, 40), (59.0, 65.0, 45), (64.0, 69.0, 50), (68.0, 74.0, 55), (73.0, 78.0, 60), (77.0, 84.0, 65), (83.0, 89.0, 70), (88.0, 94.0, 75), (93.0, 102.0, 80), (101.0, 113.0, 85), (112.0, 135.0, 90), (134.0, 155.0, 95), (154.0, _INF, 99)],
    ('Mujer', 'Fisiológica'): [(-_INF, 11.0, 5), (10.0, 13.0, 10), (12.0, 14.0, 15), (13.0, 16.0, 20), (15.0, 20.0, 25), (19.0, 23.0, 30), (22.0, 25.0, 35), (24.0, 28.0, 40), (27.0, 30.0, 45), (29.0, 33.0, 50), (32.0, 37.0, 55), (36.0, 41.0, 60), (40.0, 45.0, 65), (44.0, 49.0, 70), (48.0, 54.0, 75), (53.0, 64.0, 80), (63.0, 71.0, 85), (70.0, 94.0, 90), (93.0, 124.0, 95), (123.0, _INF, 99)],
    ('Mujer', 'Fóbica'): [(-_INF, 6.0, 5), (5.0, 9.0, 10), (8.0, 12.0, 15), (11.0, 14.0, 20), (13.0, 16.0, 25), (15.0, 20.0, 30), (19.0, 22.0, 35), (21.0, 25.0, 40), (24.0, 28.0, 45), (27.0, 31.0, 50), (30.0, 35.0, 55), (34.0, 40.0, 60), (39.0, 43.0, 65), (42.0, 48.0, 70), (47.0, 53.0, 75), (52.0, 62.0, 80), (61.0, 72.0, 85), (71.0, 86.0, 90), (85.0, 124.0, 95), (123.0, _INF, 99)],
    ('Mujer', 'Interpersonal'): [(-_INF, 4.0, 5), (3.0, 6.0, 10), (5.0, 7.0, 15), (6.0, 8.0, 20), (7.0, 9.0, 25), (8.0, 10.0, 30), (9.0, 11.0, 35), (10.0, 13.0, 40), (12.0, 14.0, 45), (13.0, 15.0, 50), (14.0, 17.0, 55), (16.0, 18.0, 60), (17.0, 21.0, 65), (20.0, 23.0, 70), (22.0, 25.0, 75), (24.0, 29.0, 80), (28.0, 33.0, 85), (32.0, 42.0, 90), (41.0, 55.0, 95), (54.0, _INF, 99)],
    ('Mujer', 'Motora'): [(-_INF, 14.0, 5), (13.0, 17.0, 10), (16.0, 21.0, 15), (20.0, 24.0, 20), (23.0, 27.0, 25), (26.0, 30.0, 30), (29.0, 33.0, 35), (32.0, 36.0, 40), (35.0, 39.0, 45), (38.0, 43.0, 50), (42.0, 47.0, 55), (46.0, 50.0, 60), (49.0, 55.0, 65), (54.0, 60.0, 70), (59.0, 65.0, 75), (64.0, 73.0, 80), (72.0, 82.0, 85), (81.0, 94.0, 90), (93.0, 121.0, 95), (120.0, _INF, 99)],
    ('Mujer', 'Total'): [(-_INF, 69.0, 5), (68.0, 80.0, 10), (79.0, 88.0, 15), (87.0, 96.0, 20), (95.0, 105.0, 25), (104.0, 112.0, 30), (111.0, 122.0, 35), (121.0, 129.0, 40), (128.0, 139.0, 45), (138.0, 148.0, 50), (147.0, 154.0, 55), (153.0, 167.0, 60), (166.0, 181.0, 65), (180.0, 194.0, 70), (193.0, 207.0, 75), (206.0, 223.0, 80), (222.0, 245.0, 85), (244.0, 299.0, 90), (298.0, 376.0, 95), (375.0, _INF, 99)],
}


def _isra_percentil(sexo, escala, pd):
    bandas = _ISRA_BAREMOS[(sexo, escala)]
    candidatos = [pct for lo, hi, pct in bandas if lo < pd < hi]
    if candidatos:
        return max(candidatos)
    # fuera de toda banda (solo posible en valores frontera): usar la más cercana
    return 99 if pd >= max(hi for _, hi, _ in bandas if hi != _INF) else 5


def _isra_apreciacion(percentil):
    if percentil < 25:
        return 'Ansiedad Mínima'
    if percentil < 80:
        return 'Ansiedad Moderada'
    if percentil < 99:
        return 'Ansiedad Severa'
    return 'Ansiedad Extrema'


def _calcular_isra(respuestas, envio=None, **kwargs):
    mapa = {r.pregunta.orden: float(r.valor_numerico or 0) for r in respuestas}

    sexo = 'Mujer'
    if envio is not None:
        try:
            if envio.paciente.sexo == 'Masculino':
                sexo = 'Hombre'
        except Exception:
            pass

    def _suma_bloque(bloque):
        ini, fin = _ISRA_BLOQUES[bloque]
        return sum(mapa.get(o, 0) for o in range(ini, fin + 1))

    pd_c = _suma_bloque('C')
    pd_f = _suma_bloque('F') / 2
    pd_m = _suma_bloque('M')
    pd_total = pd_c + pd_f + pd_m

    detalle = {}
    resumen = []
    escalas = [
        ('Cognitiva', pd_c), ('Fisiológica', pd_f),
        ('Motora', pd_m), ('Total', pd_total),
    ]
    for escala, pd in escalas:
        pct = _isra_percentil(sexo, escala, pd)
        apre = _isra_apreciacion(pct)
        pd_str = f'{pd:g}'
        detalle[f'Ansiedad {escala}' if escala != 'Total' else 'Ansiedad TOTAL'] = (
            f'PD {pd_str} — Percentil {pct} — {apre}'
        )
        resumen.append(f'{escala}: percentil {pct} ({apre})')

    for area, situaciones in _ISRA_AREAS.items():
        pd_area = sum(
            v for o, v in mapa.items()
            if _ISRA_SITUACION_POR_ORDEN.get(o) in situaciones
        )
        pct = _isra_percentil(sexo, area, pd_area)
        apre = _isra_apreciacion(pct)
        detalle[f'Área {area}'] = f'PD {pd_area:g} — Percentil {pct} — {apre}'

    detalle['Baremo aplicado'] = f'{sexo}es (según sexo registrado del paciente)'

    pct_total = _isra_percentil(sexo, 'Total', pd_total)
    interpretacion = (
        f'Ansiedad total: PD {pd_total:g}, percentil {pct_total} '
        f'({_isra_apreciacion(pct_total)}). ' + ' · '.join(resumen[:3]) + '.'
    )
    return {
        'puntaje_total': Decimal(str(round(pd_total, 2))),
        'interpretacion': interpretacion,
        'detalle': detalle,
    }


# ── Registro de calculadoras ──────────────────────────────────────────────────

_CALCULADORAS = {
    'scid2':   _calcular_scid2,
    'scl90':   _calcular_scl90,
    'allport': _calcular_allport,
    'raven':   _calcular_raven_nativo,
    'dass-21': _calcular_dass21,
    'isra':    _calcular_isra,
    'tci':     _calcular_tci,
    'tds':     _calcular_tds,
}
