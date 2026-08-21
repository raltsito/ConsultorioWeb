"""Configuración exclusiva para pruebas automatizadas.

La cadena histórica de migraciones de ``clinica`` no puede crear hoy una base
SQLite desde cero: la migración 0025 referencia una columna que no existe en
ese punto de la secuencia. Las pruebas de caracterización necesitan una base
aislada, por lo que sincronizan las tablas de ``clinica`` desde los modelos
vigentes sin alterar ni ejecutar sus migraciones de datos históricas.
"""

from .settings import *  # noqa: F403


MIGRATION_MODULES = {
    "clinica": None,
    "ventas": None,
}
