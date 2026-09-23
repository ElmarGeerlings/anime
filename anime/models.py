from django.db import models


CURATOR_TIER_CHOICES = [
    ('GOAT', 'GOAT'),
    ('S', 'S'),
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
    ('F', 'F'),
    ('DNF', 'DNF'),
]

RATING_TIER_CHOICES = [
    ('S', 'S'),
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
    ('F', 'F'),
]


class Anime(models.Model):
    STATUS_CHOICES = [
        ('ongoing', 'Ongoing'),
        ('finished', 'Finished'),
    ]

    mal_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    display_name = models.CharField(max_length=80, blank=True)
    slug = models.SlugField(unique=True)
    poster_url = models.URLField(blank=True)
    mal_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    curator_tier = models.CharField(
        max_length=4,
        choices=CURATOR_TIER_CHOICES,
        null=True,
        blank=True,
    )
    curator_rank = models.PositiveIntegerField(default=0)
    review = models.TextField(blank=True)
    jikan_synced = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def get_mal_link(self):
        if self.mal_url:
            return self.mal_url
        return f'https://myanimelist.net/anime/{self.mal_id}'

    def get_tooltip_text(self):
        if self.display_name and self.display_name != self.title:
            return f'{self.display_name} ({self.title})'
        return self.title


class DeviceProfile(models.Model):
    device_id = models.CharField(max_length=36, unique=True)
    display_name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.display_name or self.device_id


class AnimeRating(models.Model):
    device = models.ForeignKey(DeviceProfile, on_delete=models.CASCADE)
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, related_name='ratings')
    tier = models.CharField(max_length=1, choices=RATING_TIER_CHOICES)
    rating_rank = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'anime'],
                name='unique_device_anime_rating',
            ),
        ]

    def __str__(self):
        return f'{self.device} — {self.anime} ({self.tier})'


class AnimeComment(models.Model):
    device = models.ForeignKey(DeviceProfile, on_delete=models.CASCADE)
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, null=True, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.anime:
            return f'Comment on {self.anime} by {self.device}'
        return f'Guestbook comment by {self.device}'
