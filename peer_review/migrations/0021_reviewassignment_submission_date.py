# Generated by Django 2.1.15 on 2021-02-23 20:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_review', '0020_remove_reviewassignment_timer'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewassignment',
            name='submission_date',
            field=models.DateTimeField(blank=True, db_column='submission date', db_index=True, default=None, null=True),
        ),
    ]
