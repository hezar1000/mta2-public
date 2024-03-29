# Generated by Django 2.1.15 on 2022-01-04 04:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_course', '0023_courseparticipation_count_in_calculations'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='points_upon_participation_in_blue_list',
            field=models.FloatField(db_column='points_upon_participation_in_blue_list', default=10.0, null=True, verbose_name='points_upon_participation_in_blue_list'),
        ),
        migrations.AddField(
            model_name='course',
            name='points_upon_participation_in_green_list',
            field=models.FloatField(db_column='points_upon_participation_in_green_list', default=10.0, null=True, verbose_name='points_upon_participation_in_green_list'),
        ),
        migrations.AddField(
            model_name='course',
            name='points_upon_participation_in_red_list',
            field=models.FloatField(db_column='points_upon_participation_in_red_list', default=0.0, null=True, verbose_name='points_upon_participation_in_red_list'),
        ),
    ]
