from django.db import migrations

INITIAL_TERAPEUTAS = [
    {
        "nombre": "Benjamín Enrique Villagómez Castellanos",
        "titulo": "Maestría",
        "cedula": "Lic: 13696789 Mtra: En trámite",
        "preparacion": "Conducta suicida, Estrés, Ansiedad, Depresión, Violencia, TLP, Bulimia, Anorexia, Psicología organizacional, Crisis, Tanatología, Trauma, TOC",
        "formacion": "DBT, ACT, TCC, FAP, AC, MBSR, MBCT, Mindfulness, Habilidades DBT, PAPS e Intervención en crisis",
    },
    {
        "nombre": "Maricela Sena García",
        "titulo": "Licenciatura",
        "cedula": "Supervisada Arcadio: 12195628",
        "preparacion": "Estrés, Ansiedad, Depresión, Hipnosis clínica",
        "formacion": "Hipnosis clínica, TCC y DBT",
    },
    {
        "nombre": "Rosa Elena Macías Ruiz",
        "titulo": "Licenciatura",
        "cedula": "Lic: 14747476",
        "preparacion": "Estrés, Ansiedad, Depresión, Tanatología",
        "formacion": "TCC y Tanatología",
    },
    {
        "nombre": "Daniel Salazar Salazar",
        "titulo": "Licenciatura",
        "cedula": "Lic: 13951258",
        "preparacion": "Estrés, Ansiedad, Depresión, Violencia, Adicciones, Crisis",
        "formacion": "TCC, PAPS e Intervención en crisis",
    },
    {
        "nombre": "Perla Paulina Realme Nájera",
        "titulo": "Licenciatura",
        "cedula": "Lic: 13978150",
        "preparacion": "Infantil, Crianza, Salud sexual",
        "formacion": "ACT, TCC, PAPS, Intervención en crisis, Psicoterapia infantil, Psicoterapia de juego",
    },
    {
        "nombre": "María Idalia Torres Padilla",
        "titulo": "Maestría",
        "cedula": "Lic: 8859960 Mtra: En trámite",
        "preparacion": "Estrés, Ansiedad, Depresión, Parejas, Grupal, Violencia, Salud sexual",
        "formacion": "TCC",
    },
    {
        "nombre": "Daniela Sarmiento Padilla",
        "titulo": "Maestría",
        "cedula": "Lic: 14436825 Mtra: En trámite",
        "preparacion": "Estrés, Ansiedad, Depresión, Familiar, Violencia, Tanatología, Trauma",
        "formacion": "Sistémica familiar, Tanatología",
    },
    {
        "nombre": "Alisson Dibenhi Bermea Valdés",
        "titulo": "Licenciatura",
        "cedula": "Supervisada Arcadio: 12195628",
        "preparacion": "Estrés, Ansiedad, Depresión, Violencia, Adicciones, Trauma, Neurodesarrollo, TOC",
        "formacion": "Tanatología, TCC, Mindfulness, DBT",
    },
    {
        "nombre": "Francisca Esmeralda Colunga Martínez",
        "titulo": "Licenciatura",
        "cedula": "Lic: 0523003260",
        "preparacion": "Infantil, Crianza",
        "formacion": "TCC, Psicoterapia infantil, Psicoterapia de juego",
    },
    {
        "nombre": "Guadalupe Fabiola Fragoso Espinosa",
        "titulo": "Licenciatura",
        "cedula": "Lic: 14935515 Mtra: En curso",
        "preparacion": "Estrés, Ansiedad, Depresión, Tanatología",
        "formacion": "Psicoanalisis, TCC, Tanatología, Terapia breve",
    },
    {
        "nombre": "Rosa María Gomez García",
        "titulo": "Licenciatura",
        "cedula": "Lic: 0525002840",
        "preparacion": "Estrés, Ansiedad, Depresión, Tanatología",
        "formacion": "Tanatología y TCC",
    },
    {
        "nombre": "José Arcadio González Aguilar",
        "titulo": "Maestría",
        "cedula": "Lic: 12195628 Mtra: 13221359",
        "preparacion": "Estrés, Ansiedad, Depresión, Violencia, Trauma, Crisis, Conducta Suicida, TLP, Burn Out, Infantil, TOC",
        "formacion": "Gestalt, TCC, Tanatología, PAPS",
    },
    {
        "nombre": "David Bermejo Jiménez",
        "titulo": "Licenciatura",
        "cedula": "Supervisado Arcadio: 12195628",
        "preparacion": "Estrés, Ansiedad, Depresión",
        "formacion": "Gestalt",
    },
    {
        "nombre": "Javier Enrique Martínez Becerra",
        "titulo": "Licenciatura",
        "cedula": "Lic: 0518000588",
        "preparacion": "Estrés, Ansiedad, Depresión, Trauma, Crisis, Adicciones, TLP, Violencia, Conducta Suicida, TOC",
        "formacion": "PAPS, Mindfulness, TCC",
    },
    {
        "nombre": "Gloria Sarmiento Vasquez",
        "titulo": "Licenciatura",
        "cedula": "Supervisada Arcadio: 12195628",
        "preparacion": "Estrés, Ansiedad, Depresión",
        "formacion": "TCC",
    },
    {
        "nombre": "Yadira Lucía Sánchez Robles",
        "titulo": "Maestría",
        "cedula": "Lic: 2745766 Mtra: 14908716",
        "preparacion": "Estrés, Ansiedad, Depresión, Violencia",
        "formacion": "TCC",
    },
    {
        "nombre": "Marisol Guadalupe Cepeda Soto",
        "titulo": "Licenciatura",
        "cedula": "Sin cédula registrada",
        "preparacion": "Consejería",
        "formacion": "Consejería",
    },
    {
        "nombre": "Enrique Isaí Luna Jimenez",
        "titulo": "Licenciatura",
        "cedula": "Lic: 13229043",
        "preparacion": "Psiquiatría",
        "formacion": "Psiquiatría",
    },
]


def seed_forward(apps, schema_editor):
    PerfilCatalogo = apps.get_model('clinica', 'PerfilCatalogo')
    for t in INITIAL_TERAPEUTAS:
        PerfilCatalogo.objects.get_or_create(
            nombre=t['nombre'],
            defaults={
                'titulo':      t['titulo'],
                'cedula':      t['cedula'],
                'preparacion': t['preparacion'],
                'formacion':   t['formacion'],
                'activo':      True,
            }
        )


def seed_reverse(apps, schema_editor):
    PerfilCatalogo = apps.get_model('clinica', 'PerfilCatalogo')
    names = [t['nombre'] for t in INITIAL_TERAPEUTAS]
    PerfilCatalogo.objects.filter(nombre__in=names, terapeuta__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0061_perfilcatalogo'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
