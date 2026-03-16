from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clinica.models import Terapeuta
from clinica.models import quitar_tildes


CREDENTIALS = {
    "Alejandra Durán": ("alejandra.duran", "Intra!A7k2L9"),
    "Alisson Berman": ("alisson.berman", "Intra!L8c4Q7"),
    "Ana Juarez": ("ana.juarez", "Intra!C6r3W7"),
    "Benjamin Villagomez": ("benjamin.villagomez", "Intra!D9t5E1"),
    "Blanca Araceli Zamora": ("blanca.zamora", "Intra!F2y7U4"),
    "Carolina Gonzalez": ("carolina.gonzalez", "Intra!H5n9K2"),
    "Daniel Salazar": ("daniel.salazar", "Intra!J4v8L3"),
    "Daniela Sarmiento": ("daniela.sarmiento", "Intra!K7x2M5"),
    "David Bermejo": ("david.bermejo", "Intra!N8d2R5"),
    "Enrique Luna": ("enrique.luna", "Intra!Q9g3T6"),
    "Esmeralda Colunga": ("esmeralda.colunga", "Intra!R2h8V4"),
    "Fabiola Fragoso": ("fabiola.fragoso", "Intra!S5j7W1"),
    "Gloria Sarmiento": ("gloria.sarmiento", "Intra!T8k4X6"),
    "Javier Martínez": ("Javier", "Intra!U3l9Y2"),
    "Jennifer Torres": ("jennifer.torres", "Intra!V6m5Z8"),
    "José Arcadio": ("jose.arcadio", "Intra!W2n7A4"),
    "Lucía Sánchez": ("lucia.sanchez", "Intra!X9p3B6"),
    "Magda Charles": ("magda.charles", "Intra!Y4q8C1"),
    "Maria de la Luz": ("maria.de.la.luz", "Intra!Z7r2D5"),
    "Maricela Sena": ("maricela.sena", "Intra!B3t9F7"),
    "María Amancio - Par": ("maria.amancio.par", "Intra!D7v8H1"),
    "Perla Realme": ("perla.realme", "Intra!E2w5J9"),
    "Rafael Gonzalez": ("rafael.gonzalez", "Intra!F6x3K4"),
    "Rosa María Gómez": ("rosa.maria", "Intra!G9y7L2"),
    "Rosy Macías": ("rosy.macias", "Intra!H4z8M5"),
}

NAME_ALIASES = {
    "Alejandra Durán": [
        "Alejandra Duran",
        "Alejandra DurÃ¡n",
        "Alejandra Durn",
    ],
    "Alisson Berman": [
        "Alisson Bermea",
    ],
    "Javier Martínez": [
        "Javier Martinez",
        "Javier MartÃ­nez",
        "Javier Martnez",
    ],
    "José Arcadio": [
        "Jose Arcadio",
        "JosÃ© Arcadio",
        "Jos Arcadio",
    ],
    "Lucía Sánchez": [
        "Lucia Sanchez",
        "LucÃ­a SÃ¡nchez",
        "Lucia SÃ¡nchez",
        "Luca Sánchez",
    ],
    "María Amancio - Ind": [
        "Maria Amancio - Ind",
        "MarÃ­a Amancio - Ind",
        "Mara Amancio - Ind",
    ],
    "María Amancio - Par": [
        "Maria Amancio - Par",
        "MarÃ­a Amancio - Par",
        "Mara Amancio - Par",
    ],
    "Rosy Macías": [
        "Rosy Macias",
        "Rosy MacÃ­as",
        "Rosy Macas",
    ],
}


class Command(BaseCommand):
    help = "Crea o resetea accesos para terapeutas y los enlaza a su perfil."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra los cambios sin escribir en la base de datos.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        terapeutas = list(Terapeuta.objects.all().order_by("nombre"))
        terapeutas_por_nombre = {quitar_tildes(t.nombre): t for t in terapeutas}
        encontrados = {}
        faltantes = []

        for nombre in CREDENTIALS:
            candidatos = [nombre] + NAME_ALIASES.get(nombre, [])
            terapeuta = None
            for candidato in candidatos:
                terapeuta = terapeutas_por_nombre.get(quitar_tildes(candidato))
                if terapeuta is not None:
                    break
            if terapeuta is None:
                faltantes.append(nombre)
                continue
            encontrados[nombre] = terapeuta

        if faltantes:
            raise CommandError(f"No se encontraron terapeutas: {', '.join(faltantes)}")

        for nombre, terapeuta in encontrados.items():
            username, password = CREDENTIALS[nombre]
            usuario = User.objects.filter(username=username).first()
            if not dry_run:
                if usuario is None:
                    usuario = User(username=username)
                usuario.set_password(password)
                usuario.first_name = nombre
                usuario.is_active = True
                usuario.save()
                terapeuta.usuario = usuario
                terapeuta.activo = True
                terapeuta.save(update_fields=["usuario", "activo"])
            self.stdout.write(f"{nombre} | {username} | {password}")

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run: no se escribieron cambios."))
        else:
            self.stdout.write(self.style.SUCCESS("Accesos de terapeutas actualizados."))
