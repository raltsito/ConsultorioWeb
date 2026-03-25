from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0027_documento_binario_en_db'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudcita',
            name='consultorio',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='clinica.consultorio',
            ),
        ),
    ]
