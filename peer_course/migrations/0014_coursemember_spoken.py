# Generated by Django 2.1.15 on 2021-09-16 03:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_course', '0013_coursemember_hand_up'),
    ]

    operations = [
        migrations.AddField(
            model_name='coursemember',
            name='spoken',
            field=models.BooleanField(db_column='spoken', db_index=True, default=False, verbose_name='spoken'),
        ),
    ]