# Generated by Django 2.1.5 on 2019-08-29 16:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_assignment', '0014_auto_20190813_1355'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='max_total_grade',
            field=models.FloatField(blank=True, default=0),
        ),
    ]