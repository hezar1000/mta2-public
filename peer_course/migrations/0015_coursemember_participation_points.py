# Generated by Django 2.1.15 on 2021-09-16 03:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_course', '0014_coursemember_spoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='coursemember',
            name='participation_points',
            field=models.IntegerField(db_column='participation_points', default=0, null=True, verbose_name='participation_points'),
        ),
    ]
