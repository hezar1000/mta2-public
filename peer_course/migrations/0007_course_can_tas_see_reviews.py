# Generated by Django 2.1.5 on 2019-01-27 00:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_course", "0006_merge_20190126_1442")]

    operations = [
        migrations.AddField(
            model_name="course",
            name="can_tas_see_reviews",
            field=models.BooleanField(default=False),
        )
    ]
