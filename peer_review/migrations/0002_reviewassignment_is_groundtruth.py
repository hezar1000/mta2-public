# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-08-10 18:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_review", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="reviewassignment",
            name="is_groundtruth",
            field=models.BooleanField(
                db_column="is_groundtruth",
                default=False,
                verbose_name="is_groundtruth?",
            ),
        )
    ]
