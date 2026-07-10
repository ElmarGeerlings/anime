import sys

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from urllib.error import HTTPError, URLError

from anime.models import Anime
from anime.services import (
    get_anime_metadata,
    load_seed_label_map,
    load_seed_metadata,
    status_for_mal_id,
    sync_all_anime_statuses,
)

# String = Jikan search label. (label, mal_id) = explicit MAL id (use when search is ambiguous).
CURATOR_TIERLIST = {
    'GOAT': [
        ('One Piece', 21),
        'Naruto',
        'Dragon Ball',
    ],
    'S': [
        'Mob Psycho 100',
        'Grand Blue',
        'Space Dandy',
        'Frieren: Beyond Journey\'s End',
    ],
    'A': [
        'Attack on Titan',
        'Death Note',
        'Steins;Gate',
        'Vinland Saga',
        'Oshi no Ko',
        'Hunter x Hunter (2011)',
    ],
    'B': [
        'Dandadan',
        'Bocchi the Rock!',
        'Re:Zero',
        'Jujutsu Kaisen',
        'Chainsaw Man',
        'Made in Abyss',
    ],
    'C': [
        'Asobi Asobase',
        'Mushishi',
        "JoJo's Bizarre Adventure",
        'Odd Taxi',
        'Gachiakuta',
        'Cowboy Bebop',
        'Solo Leveling',
        'Great Teacher Onizuka',
        'Code Geass: Lelouch of the Rebellion',
    ],
    'D': [
        'Fullmetal Alchemist: Brotherhood',
        'Chi. Chikyuu no Undou ni Tsuite',
        'One Punch Man',
        'Dumbbell Nan Kilo Moteru?',
        'Kids on the Slope',
        'Blue Lock',
        'Uma Musume: Cinderella Gray',
        'Initial D First Stage',
        ('Monster', 19),
        'Assassination Classroom',
        'Daily Lives of High School Boys',
        'Kaiju No. 8',
        'Baccano!',
    ],
    'E': [
        'Cyberpunk: Edgerunners',
        'Tengen Toppa Gurren Lagann',
        'Tokyo Ghoul',
        'Trigun Stampede',
        'The Future Diary',
        'Samurai Champloo',
        'Death Parade',
        'Lazarus',
        'Chio-chan no Tsuugakuro',
    ],
    'F': [
        'From the New World',
        'Pluto',
        'Neon Genesis Evangelion',
        'Black Lagoon',
        'Hellsing Ultimate',
    ],
    'DNF': [
        'Baki',
        'Nichijou',
        'Durarara!!',
        'Pop Team Epic',
    ],
}

# Wrong rows from earlier bad ids / bad search — remove from curator list
ORPHAN_MAL_IDS = [
    459,    # One Piece Movie 01
    31758,  # Kizumonogatari
    30240,  # Prison School
    49053,  # Given: Uragawa no Sonzai
    59192,  # Kimetsu movie
    37969,  # Youkai Watch movie
    2594,   # Piano no Mori
    48569,  # 86 Part 2
    58392,  # Hanbun Otona
    61629,  # Monster (Music, 2025)
    6,      # Trigun (1998) — use Stampede
    270,    # Hellsing TV — use Ultimate
]


def safe_write(command, msg, style=None):
    encoding = getattr(command.stdout, 'encoding', None) or sys.stdout.encoding or 'utf-8'
    safe_msg = msg.encode(encoding, errors='replace').decode(encoding)
    if style:
        command.stdout.write(style(safe_msg))
    else:
        command.stdout.write(safe_msg)


def parse_tier_entry(entry):
    if isinstance(entry, tuple):
        return entry[0], entry[1]
    return entry, None


def unique_slug(title, mal_id):
    base = slugify(title) or f'anime-{mal_id}'
    slug = base
    n = 2
    while Anime.objects.filter(slug=slug).exclude(mal_id=mal_id).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


class Command(BaseCommand):
    help = 'Seed curator tier list — resolves anime by Jikan search, caches mal_id + metadata'

    def add_arguments(self, parser):
        parser.add_argument(
            '--refresh',
            action='store_true',
            help='Re-fetch from Jikan even when anime already exists in DB',
        )
        parser.add_argument(
            '--re-resolve',
            action='store_true',
            help='Re-run Jikan search for labels (ignore label_to_mal_id.json)',
        )

    def handle(self, *args, **options):
        refresh = options['refresh']
        re_resolve = options['re_resolve']
        created = 0
        updated = 0
        skipped = 0
        failed = 0
        pruned = 0
        metadata = load_seed_metadata()
        label_map = load_seed_label_map()
        seeded_mal_ids = []

        pruned = Anime.objects.filter(mal_id__in=ORPHAN_MAL_IDS).update(
            curator_tier=None,
            curator_rank=0,
        )
        if pruned:
            safe_write(self, f'Pruned {pruned} wrong anime from curator list.')

        for tier, entries in CURATOR_TIERLIST.items():
            self.stdout.write(f'\n{tier}:')
            for idx, entry in enumerate(entries, start=1):
                label, mal_id_override = parse_tier_entry(entry)
                try:
                    mal_id, jikan_data, label_map, metadata = resolve_seed_anime(
                        label,
                        label_map,
                        metadata,
                        refresh=re_resolve,
                        mal_id_override=mal_id_override,
                    )
                except (HTTPError, URLError) as ex:
                    failed += 1
                    code = ex.code if isinstance(ex, HTTPError) else 'network'
                    safe_write(self, self.style.ERROR(
                        f'  Failed ({code}): {label} — re-run later to retry'
                    ))
                    continue

                if mal_id is None or jikan_data is None:
                    failed += 1
                    safe_write(self, self.style.ERROR(
                        f'  No search results for: {label}'
                    ))
                    continue

                seeded_mal_ids.append(mal_id)

                existing = Anime.objects.filter(mal_id=mal_id).first()
                if existing and not refresh:
                    existing.curator_tier = tier
                    existing.curator_rank = idx
                    existing.status = status_for_mal_id(mal_id)
                    existing.save(update_fields=['curator_tier', 'curator_rank', 'status'])
                    skipped += 1
                    safe_write(self,
                        f'  Skipped (exists): {existing.title} ({mal_id}) <- {label} -> {tier} #{idx}'
                    )
                    continue

                anime, is_new = Anime.objects.get_or_create(
                    mal_id=mal_id,
                    defaults={
                        'slug': unique_slug(jikan_data['title'], mal_id),
                        'curator_tier': tier,
                        'curator_rank': idx,
                    },
                )
                anime.title = jikan_data['title']
                anime.poster_url = jikan_data['poster_url']
                anime.mal_url = jikan_data['mal_url']
                anime.status = status_for_mal_id(mal_id)
                anime.curator_tier = tier
                anime.curator_rank = idx
                if not anime.slug:
                    anime.slug = unique_slug(jikan_data['title'], mal_id)
                anime.save()

                if is_new:
                    created += 1
                    action = 'Created'
                else:
                    updated += 1
                    action = 'Updated'
                safe_write(self,
                    f'  {action}: {anime.title} ({mal_id}) <- {label} -> {tier} #{idx}'
                )

        sync_all_anime_statuses()

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. {created} created, {updated} updated, {skipped} skipped, {failed} failed.'
        ))
        if failed:
            self.stdout.write('Re-run the same command to retry failed/missing entries.')
