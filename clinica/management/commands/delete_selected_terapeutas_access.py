from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from clinica.models import Terapeuta


USERNAMES_TO_DELETE = [
    "maria.amancio.ind",
    "alondra.escalon",
    "carlos.mendiola",
    "dante.zertuche",
    "dante.zertuche.ev",
    "enrique.arteaga",
    "mariana.siller",
    "yessica.leija",
    "terapeuta.prueba",
]


class Command(BaseCommand):
    help = "Borra accesos seleccionados de terapeutas y desenlaza los perfiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra que usuarios se borrarian.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        usuarios = list(User.objects.filter(username__in=USERNAMES_TO_DELETE))

        for usuario in usuarios:
            Terapeuta.objects.filter(usuario=usuario).update(usuario=None)
            self.stdout.write(f"{usuario.username}")
            if not dry_run:
                usuario.delete()

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run: no se borro nada."))
        else:
            self.stdout.write(self.style.SUCCESS("Accesos seleccionados eliminados."))
