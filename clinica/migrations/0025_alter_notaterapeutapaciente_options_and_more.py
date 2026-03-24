from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0024_notaterapeutapaciente'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        "ALTER TABLE clinica_notaterapeutapaciente RENAME COLUMN actualizado_en TO creado_en;",
                        "DROP INDEX IF EXISTS clinica_notaterapeutapaciente_terapeuta_id_paciente_id_ec79bb89_uniq;",
                    ],
                    reverse_sql=[
                        "CREATE UNIQUE INDEX IF NOT EXISTS clinica_notaterapeutapaciente_terapeuta_id_paciente_id_ec79bb89_uniq ON clinica_notaterapeutapaciente (terapeuta_id, paciente_id);",
                        "ALTER TABLE clinica_notaterapeutapaciente RENAME COLUMN creado_en TO actualizado_en;",
                    ],
                ),
            ],
            state_operations=[],
        ),
    ]
