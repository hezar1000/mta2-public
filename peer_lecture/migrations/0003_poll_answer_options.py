# Generated by Django 2.1.15 on 2023-09-02 00:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_lecture', '0002_auto_20230901_1242'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='answer_options',
            field=models.TextField(null=True),
        ),
    ]