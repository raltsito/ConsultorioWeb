from django.db import migrations, models


def limpiar_viene_acompanante(apps, schema_editor):
    AperturaExpediente = apps.get_model('clinica', 'AperturaExpediente')
    AperturaExpediente.objects.filter(viene_acompanante='').update(viene_acompanante=False)
    AperturaExpediente.objects.filter(viene_acompanante=None).update(viene_acompanante=False)


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0106_aperturaexpediente_acompanante_nombre_and_more'),
    ]

    operations = [
        migrations.RunPython(limpiar_viene_acompanante, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='aperturaexpediente',
            name='viene_acompanante',
            field=models.BooleanField(default=False, verbose_name='¿Viene acompañado?'),
        ),
    ]
