import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from anime.models import Anime, RATING_TIER_CHOICES
from anime.services import (
    get_anime_community_stats,
    get_community_animes,
    get_community_by_tier,
    get_curator_by_tier,
    get_personal_maker_by_tier,
    get_unrated_pool,
    get_user_rating,
    save_personal_tierlist,
    save_rating,
)


def tier_list(request):
    device_id = request.COOKIES.get('anime_device_id', '')
    community_animes = get_community_animes()
    ctx = {
        'curator_by_tier': get_curator_by_tier(),
        'community_by_tier': get_community_by_tier(),
        'has_community_ratings': community_animes.exists(),
        'personal_by_tier': get_personal_maker_by_tier(device_id),
        'unrated_pool': get_unrated_pool(device_id),
    }
    return render(request, 'anime/tier_list.html', ctx)


def anime_detail(request, slug):
    device_id = request.COOKIES.get('anime_device_id', '')
    anime = get_object_or_404(Anime, slug=slug)
    ctx = {
        'anime': anime,
        'rating_tiers': RATING_TIER_CHOICES,
        'user_rating': get_user_rating(device_id, anime),
        'community_stats': get_anime_community_stats(anime),
    }
    return render(request, 'anime/detail.html', ctx)


@require_POST
def rate(request):
    device_id = request.POST['device_id']
    tier = request.POST['tier']
    display_name = request.POST.get('display_name', '')
    anime = get_object_or_404(Anime, pk=request.POST['anime_id'])
    save_rating(device_id, display_name, anime, tier)
    response = redirect('anime_detail', slug=anime.slug)
    response.set_cookie('anime_device_id', device_id, max_age=365 * 24 * 60 * 60, samesite='Lax')
    return response


@require_POST
def save_tierlist(request):
    device_id = request.POST['device_id']
    tiers = json.loads(request.POST['tiers'])
    save_personal_tierlist(device_id, tiers)
    response = JsonResponse({'ok': True})
    response.set_cookie('anime_device_id', device_id, max_age=365 * 24 * 60 * 60, samesite='Lax')
    return response
