# Generated by Django 2.1.15 on 2023-09-01 19:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('peer_lecture', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='poll',
            old_name='poll_text',
            new_name='poll_data',
        ),
    ]
