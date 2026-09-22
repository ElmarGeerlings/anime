from django.contrib import admin, messages

from anime.models import Anime, AnimeComment, AnimeRating, DeviceProfile
from anime.services import apply_curator_rank_insert, try_sync_anime_from_jikan


@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ['title', 'curator_tier', 'curator_rank', 'status', 'mal_id', 'jikan_synced', 'added_at']
    list_filter = ['curator_tier', 'status', 'jikan_synced']
    search_fields = ['title', 'slug', 'mal_id']
    ordering = ['curator_tier', 'curator_rank', 'title']
    readonly_fields = ['jikan_synced']

    def save_model(self, request, obj, form, change):
        if change:
            previous = Anime.objects.filter(pk=obj.pk).first()
            if previous and previous.mal_id != obj.mal_id:
                obj.jikan_synced = False
        apply_curator_rank_insert(obj, change)
        super().save_model(request, obj, form, change)
        if try_sync_anime_from_jikan(obj):
            obj.save(update_fields=['title', 'poster_url', 'mal_url', 'status', 'jikan_synced'])
        else:
            obj.save(update_fields=['jikan_synced'])
            messages.warning(
                request,
                'Saved, but MAL metadata could not be refreshed. Will retry via sync command.',
            )


admin.site.register(DeviceProfile)
admin.site.register(AnimeRating)
admin.site.register(AnimeComment)
