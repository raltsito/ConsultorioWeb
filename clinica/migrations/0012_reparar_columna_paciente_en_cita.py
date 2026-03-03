from django.db import migrations


def reparar_columna_paciente(apps, schema_editor):
    connection = schema_editor.connection
    introspection = connection.introspection
    tables = set(introspection.table_names())

    if "clinica_cita" not in tables:
        return

    with connection.cursor() as cursor:
        columnas = {
            col.name for col in introspection.get_table_description(cursor, "clinica_cita")
        }

        # Si la columna paciente_id desaparecio (por migracion previa), la volvemos a crear.
        if "paciente_id" not in columnas:
            tipo_columna = "bigint" if connection.vendor == "postgresql" else "integer"
            cursor.execute(
                f'ALTER TABLE "clinica_cita" ADD COLUMN "paciente_id" {tipo_columna} NULL'
            )

        # Si existe la tabla M2M, usamos el primer paciente relacionado para recuperar datos.
        if "clinica_cita_pacientes" in tables:
            cursor.execute(
                """
                UPDATE "clinica_cita" c
                SET "paciente_id" = sub."paciente_id"
                FROM (
                    SELECT "cita_id", MIN("paciente_id") AS "paciente_id"
                    FROM "clinica_cita_pacientes"
                    GROUP BY "cita_id"
                ) sub
                WHERE c."id" = sub."cita_id"
                  AND c."paciente_id" IS NULL
                """
            )

        # Ultimo respaldo: si todavia hay citas sin paciente, asignamos el primer paciente existente.
        if "clinica_paciente" in tables:
            cursor.execute('SELECT "id" FROM "clinica_paciente" ORDER BY "id" ASC LIMIT 1')
            primer_paciente = cursor.fetchone()
            if primer_paciente:
                cursor.execute(
                    'UPDATE "clinica_cita" SET "paciente_id" = %s WHERE "paciente_id" IS NULL',
                    [primer_paciente[0]],
                )


def noop_reverse(apps, schema_editor):
    # Migracion de reparacion: no revertimos automaticamente.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0010_solicitudcita"),
    ]

    operations = [
        migrations.RunPython(reparar_columna_paciente, noop_reverse),
    ]
