# Generated by Django 2.1.15 on 2023-09-07 21:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('peer_lecture', '0010_poll_is_duplicate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='poll',
            name='is_duplicate',
        ),
        migrations.AddField(
            model_name='poll',
            name='duplicate_of',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='peer_lecture.Poll'),
        ),
    ]