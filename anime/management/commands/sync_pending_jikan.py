from django.core.management.base import BaseCommand

from anime.services import sync_pending_jikan_animes


class Command(BaseCommand):
    help = 'Fetch MAL metadata from Jikan for anime with jikan_synced=False'

    def handle(self, *args, **options):
        result = sync_pending_jikan_animes()
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. {result["synced"]} synced, {result["failed"]} failed, '
                f'{result["total"]} total pending.'
            )
        )
