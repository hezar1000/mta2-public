# Generated by Django 2.1.15 on 2023-09-02 22:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_lecture', '0006_auto_20230902_1535'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='poll',
            name='use_date',
        ),
        migrations.AlterField(
            model_name='poll',
            name='start_time',
            field=models.DateTimeField(null=True),
        ),
    ]