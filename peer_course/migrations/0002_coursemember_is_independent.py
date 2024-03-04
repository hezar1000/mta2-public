# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-08-15 00:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_course", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="coursemember",
            name="is_independent",
            field=models.BooleanField(
                db_column="is_independent",
                default=False,
                verbose_name="is_independent?",
            ),
        )
    ]
