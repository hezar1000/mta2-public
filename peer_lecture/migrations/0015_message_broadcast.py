# Generated by Django 2.1.15 on 2023-09-09 21:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_lecture', '0014_auto_20230909_1436'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='broadcast',
            field=models.BooleanField(default=False),
        ),
    ]