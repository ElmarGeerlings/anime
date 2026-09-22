import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from django.db import transaction
from django.db.models import Avg, Case, Count, IntegerField, When
from django.db.models import F

from anime.models import Anime, AnimeRating, CURATOR_TIER_CHOICES, DeviceProfile, RATING_TIER_CHOICES

TIER_TO_SCORE = {'S': 6, 'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1, 'F': 0}
SCORE_TO_TIER = {6: 'S', 5: 'A', 4: 'B', 3: 'C', 2: 'D', 1: 'E', 0: 'F'}

CURATOR_TIER_ORDER = [choice[0] for choice in CURATOR_TIER_CHOICES]
COMMUNITY_TIER_ORDER = [choice[0] for choice in RATING_TIER_CHOICES]

SEED_METADATA_PATH = Path(__file__).resolve().parent / 'seed_data' / 'metadata.json'
SEED_LABEL_MAP_PATH = Path(__file__).resolve().parent / 'seed_data' / 'label_to_mal_id.json'
JIKAN_RETRY_CODES = {429}
JIKAN_REQUEST_DELAY = 1.5

# Curator-maintained — Jikan airing flag only reflects one season entry
ONGOING_MAL_IDS = frozenset([
    21,     # One Piece
    37105,  # Grand Blue
    52991,  # Frieren
    37521,  # Vinland Saga
    52034,  # Oshi no Ko
    57334,  # Dandadan
    47917,  # Bocchi the Rock!
    31240,  # Re:Zero
    40748,  # Jujutsu Kaisen
    44511,  # Chainsaw Man
    34599,  # Made in Abyss
    14719,  # JoJo
    59062,  # Gachiakuta
    52299,  # Solo Leveling
    30276,  # One Punch Man
    49596,  # Blue Lock
    59636,  # Uma Musume: Cinderella Gray
    52588,  # Kaiju No. 8
    42310,  # Cyberpunk: Edgerunners
])


def status_for_mal_id(mal_id):
    if mal_id in ONGOING_MAL_IDS:
        return 'ongoing'
    return 'finished'


def sync_all_anime_statuses():
    Anime.objects.filter(mal_id__in=ONGOING_MAL_IDS).update(status='ongoing')
    Anime.objects.exclude(mal_id__in=ONGOING_MAL_IDS).update(status='finished')


def attach_ongoing_flags(animes):
    for anime in animes:
        anime.is_ongoing = anime.mal_id in ONGOING_MAL_IDS
    return animes


def score_to_community_tier(avg_score):
    rounded = int(avg_score + 0.5)
    rounded = max(0, min(6, rounded))
    return SCORE_TO_TIER[rounded]


def load_seed_metadata():
    if not SEED_METADATA_PATH.exists():
        return {}
    with SEED_METADATA_PATH.open(encoding='utf-8') as metadata_file:
        raw = json.load(metadata_file)
    return {int(mal_id): value for mal_id, value in raw.items()}


def save_seed_metadata(metadata):
    SEED_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        str(mal_id): value
        for mal_id, value in sorted(metadata.items(), key=lambda item: item[0])
    }
    with SEED_METADATA_PATH.open('w', encoding='utf-8') as metadata_file:
        json.dump(serializable, metadata_file, indent=2)
        metadata_file.write('\n')


def load_seed_label_map():
    if not SEED_LABEL_MAP_PATH.exists():
        return {}
    with SEED_LABEL_MAP_PATH.open(encoding='utf-8') as label_map_file:
        return json.load(label_map_file)


def save_seed_label_map(label_map):
    SEED_LABEL_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SEED_LABEL_MAP_PATH.open('w', encoding='utf-8') as label_map_file:
        json.dump(label_map, label_map_file, indent=2, sort_keys=True)
        label_map_file.write('\n')


def parse_jikan_anime_payload(data):
    return {
        'title': data['title'],
        'poster_url': data['images']['jpg']['image_url'],
        'mal_url': data['url'],
        'status': 'ongoing' if data['airing'] else 'finished',
    }


def jikan_get_json(url, max_attempts=5):
    wait_seconds = 2
    for attempt in range(max_attempts):
        try:
            with urlopen(url) as response:
                return json.load(response)
        except HTTPError as ex:
            if ex.code not in JIKAN_RETRY_CODES or attempt == max_attempts - 1:
                raise
            time.sleep(wait_seconds)
            wait_seconds = wait_seconds * 2


def fetch_anime_from_jikan(mal_id, max_attempts=5):
    url = f'https://api.jikan.moe/v4/anime/{mal_id}'
    payload = jikan_get_json(url, max_attempts=max_attempts)
    return parse_jikan_anime_payload(payload['data'])


def search_anime_from_jikan(query, limit=5, max_attempts=5):
    url = f'https://api.jikan.moe/v4/anime?q={quote(query)}&limit={limit}'
    payload = jikan_get_json(url, max_attempts=max_attempts)
    results = []
    for item in payload['data']:
        entry = parse_jikan_anime_payload(item)
        entry['mal_id'] = item['mal_id']
        results.append(entry)
    return results


def get_anime_metadata(mal_id, metadata, fetch_missing=True):
    if mal_id in metadata:
        return metadata[mal_id], metadata
    if not fetch_missing:
        return None, metadata
    jikan_data = fetch_anime_from_jikan(mal_id)
    metadata[mal_id] = jikan_data
    save_seed_metadata(metadata)
    time.sleep(JIKAN_REQUEST_DELAY)
    return jikan_data, metadata


def resolve_seed_anime(label, label_map, metadata, refresh=False, mal_id_override=None):
    mal_id = mal_id_override
    if mal_id is not None:
        mal_id = int(mal_id)
        label_map[label] = mal_id
        save_seed_label_map(label_map)
    elif not refresh and label in label_map:
        mal_id = int(label_map[label])

    if mal_id is None:
        results = search_anime_from_jikan(label, limit=1)
        time.sleep(JIKAN_REQUEST_DELAY)
        if not results:
            return None, None, label_map, metadata
        match = results[0]
        mal_id = match['mal_id']
        label_map[label] = mal_id
        save_seed_label_map(label_map)
        metadata[mal_id] = {
            'title': match['title'],
            'poster_url': match['poster_url'],
            'mal_url': match['mal_url'],
            'status': match['status'],
        }
        save_seed_metadata(metadata)
        return mal_id, metadata[mal_id], label_map, metadata

    if mal_id in metadata and not refresh:
        return mal_id, metadata[mal_id], label_map, metadata

    jikan_data, metadata = get_anime_metadata(mal_id, metadata, fetch_missing=True)
    return mal_id, jikan_data, label_map, metadata


def sync_anime_from_jikan(anime):
    jikan_data = fetch_anime_from_jikan(anime.mal_id)
    anime.title = jikan_data['title']
    anime.poster_url = jikan_data['poster_url']
    anime.mal_url = jikan_data['mal_url']
    anime.status = status_for_mal_id(anime.mal_id)
    return anime


def try_sync_anime_from_jikan(anime):
    try:
        sync_anime_from_jikan(anime)
    except (HTTPError, URLError):
        anime.jikan_synced = False
        return False
    anime.jikan_synced = True
    return True


def sync_pending_jikan_animes():
    pending = Anime.objects.filter(jikan_synced=False).order_by('pk')
    total = pending.count()
    synced = 0
    failed = 0
    update_fields = ['title', 'poster_url', 'mal_url', 'status', 'jikan_synced']
    for anime in pending:
        if try_sync_anime_from_jikan(anime):
            anime.save(update_fields=update_fields)
            synced += 1
        else:
            anime.save(update_fields=['jikan_synced'])
            failed += 1
        time.sleep(JIKAN_REQUEST_DELAY)
    return {'synced': synced, 'failed': failed, 'total': total}


def apply_curator_rank_insert(anime, change):
    new_tier = anime.curator_tier
    new_rank = anime.curator_rank
    if new_rank < 1:
        new_rank = 1

    previous = None
    if change:
        previous = Anime.objects.get(pk=anime.pk)

    with transaction.atomic():
        if not previous:
            if not new_tier:
                anime.curator_rank = 0
                return anime
            tier_qs = Anime.objects.filter(curator_tier=new_tier)
            max_rank = tier_qs.count() + 1
            if new_rank > max_rank:
                new_rank = max_rank
            tier_qs.filter(curator_rank__gte=new_rank).update(curator_rank=F('curator_rank') + 1)
            anime.curator_rank = new_rank
            return anime

        old_tier = previous.curator_tier
        old_rank = previous.curator_rank

        if old_tier == new_tier:
            if not new_tier:
                anime.curator_rank = 0
                return anime
            tier_qs = Anime.objects.filter(curator_tier=new_tier).exclude(pk=anime.pk)
            max_rank = tier_qs.count() + 1
            if new_rank > max_rank:
                new_rank = max_rank
            if new_rank < old_rank:
                tier_qs.filter(curator_rank__gte=new_rank, curator_rank__lt=old_rank).update(
                    curator_rank=F('curator_rank') + 1
                )
            if new_rank > old_rank:
                tier_qs.filter(curator_rank__gt=old_rank, curator_rank__lte=new_rank).update(
                    curator_rank=F('curator_rank') - 1
                )
            anime.curator_rank = new_rank
            return anime

        if old_tier:
            Anime.objects.filter(curator_tier=old_tier, curator_rank__gt=old_rank).update(
                curator_rank=F('curator_rank') - 1
            )

        if not new_tier:
            anime.curator_rank = 0
            return anime

        target_qs = Anime.objects.filter(curator_tier=new_tier).exclude(pk=anime.pk)
        max_rank = target_qs.count() + 1
        if new_rank > max_rank:
            new_rank = max_rank
        target_qs.filter(curator_rank__gte=new_rank).update(curator_rank=F('curator_rank') + 1)
        anime.curator_rank = new_rank
        return anime


def group_by_tier(animes, tier_order, tier_attr):
    buckets = {tier: [] for tier in tier_order}
    for anime in animes:
        tier = getattr(anime, tier_attr)
        if tier in buckets:
            buckets[tier].append(anime)
    return [(tier, buckets[tier]) for tier in tier_order]


def get_curator_tier_list():
    return Anime.objects.filter(curator_tier__isnull=False).order_by('curator_rank', 'title')


def get_curator_by_tier():
    animes = attach_ongoing_flags(list(get_curator_tier_list()))
    return group_by_tier(animes, CURATOR_TIER_ORDER, 'curator_tier')


def get_community_animes():
    tier_score = Case(
        When(ratings__tier='S', then=6),
        When(ratings__tier='A', then=5),
        When(ratings__tier='B', then=4),
        When(ratings__tier='C', then=3),
        When(ratings__tier='D', then=2),
        When(ratings__tier='E', then=1),
        When(ratings__tier='F', then=0),
        output_field=IntegerField(),
    )
    return (
        Anime.objects.annotate(
            rating_count=Count('ratings'),
            avg_score=Avg(tier_score),
        )
        .filter(rating_count__gte=1)
        .order_by('-avg_score', 'title')
    )


def attach_community_tiers(animes):
    for anime in animes:
        anime.community_tier = score_to_community_tier(anime.avg_score)
    return animes


def get_community_by_tier():
    animes = attach_community_tiers(attach_ongoing_flags(list(get_community_animes())))
    return group_by_tier(animes, COMMUNITY_TIER_ORDER, 'community_tier')


def get_or_create_device_profile(device_id, display_name=''):
    profile, created = DeviceProfile.objects.get_or_create(device_id=device_id)
    if created:
        profile.display_name = f'User {profile.pk}'
        profile.save(update_fields=['display_name'])
    if display_name and display_name.strip() and display_name.strip() != profile.display_name:
        profile.display_name = display_name.strip()
        profile.save(update_fields=['display_name'])
    return profile


def save_rating(device_id, display_name, anime, tier):
    profile = get_or_create_device_profile(device_id, display_name)
    existing = AnimeRating.objects.filter(device=profile, anime=anime).first()
    if existing and existing.tier == tier:
        return
    max_rank = AnimeRating.objects.filter(device=profile, tier=tier).count()
    AnimeRating.objects.update_or_create(
        device=profile,
        anime=anime,
        defaults={'tier': tier, 'rating_rank': max_rank + 1},
    )


def get_personal_maker_by_tier(device_id):
    animes = []
    profile = DeviceProfile.objects.filter(device_id=device_id).first()
    if profile:
        tier_order = Case(
            When(tier='S', then=0),
            When(tier='A', then=1),
            When(tier='B', then=2),
            When(tier='C', then=3),
            When(tier='D', then=4),
            When(tier='E', then=5),
            When(tier='F', then=6),
            output_field=IntegerField(),
        )
        ratings = (
            AnimeRating.objects.filter(device=profile)
            .select_related('anime')
            .order_by(tier_order, 'rating_rank', 'anime__title')
        )
        for rating in ratings:
            anime = rating.anime
            anime.personal_tier = rating.tier
            animes.append(anime)
    animes = attach_ongoing_flags(animes)
    return group_by_tier(animes, COMMUNITY_TIER_ORDER, 'personal_tier')


def get_unrated_pool(device_id):
    rated_ids = AnimeRating.objects.filter(device__device_id=device_id).values_list('anime_id', flat=True)
    pool = Anime.objects.filter(curator_tier__isnull=False).exclude(pk__in=rated_ids).order_by('title')
    return attach_ongoing_flags(list(pool))


def save_personal_tierlist(device_id, tiers_map):
    profile = get_or_create_device_profile(device_id)
    placed_ids = set()
    for tier in COMMUNITY_TIER_ORDER:
        anime_ids = tiers_map.get(tier, [])
        for rank, anime_id in enumerate(anime_ids, start=1):
            anime_id = int(anime_id)
            placed_ids.add(anime_id)
            AnimeRating.objects.update_or_create(
                device=profile,
                anime_id=anime_id,
                defaults={'tier': tier, 'rating_rank': rank},
            )
    AnimeRating.objects.filter(device=profile).exclude(anime_id__in=placed_ids).delete()


def get_personal_by_tier(device_id):
    if not device_id:
        return [], False
    profile = DeviceProfile.objects.filter(device_id=device_id).first()
    if not profile:
        return [], False
    if not AnimeRating.objects.filter(device=profile).exists():
        return [], False
    return get_personal_maker_by_tier(device_id), True


def get_user_rating(device_id, anime):
    profile = DeviceProfile.objects.filter(device_id=device_id).first()
    if not profile:
        return None
    rating = AnimeRating.objects.filter(device=profile, anime=anime).first()
    if not rating:
        return None
    return rating.tier


def get_anime_community_stats(anime):
    ratings = list(anime.ratings.all())
    if not ratings:
        return None
    scores = [TIER_TO_SCORE[rating.tier] for rating in ratings]
    avg_score = sum(scores) / len(scores)
    return {
        'rating_count': len(ratings),
        'avg_score': avg_score,
        'community_tier': score_to_community_tier(avg_score),
    }
