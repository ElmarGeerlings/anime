from django.contrib import admin

from anime.models import Anime, AnimeComment, AnimeRating, DeviceProfile
from anime.services import apply_curator_rank_insert, sync_anime_from_jikan


@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ['title', 'curator_tier', 'curator_rank', 'status', 'mal_id', 'added_at']
    list_filter = ['curator_tier', 'status']
    search_fields = ['title', 'slug', 'mal_id']
    ordering = ['curator_tier', 'curator_rank', 'title']

    def save_model(self, request, obj, form, change):
        sync_anime_from_jikan(obj)
        apply_curator_rank_insert(obj, change)
        super().save_model(request, obj, form, change)


admin.site.register(DeviceProfile)
admin.site.register(AnimeRating)
admin.site.register(AnimeComment)
