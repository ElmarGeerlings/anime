from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anime', '0004_anime_jikan_synced'),
    ]

    operations = [
        migrations.AddField(
            model_name='anime',
            name='display_name',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
