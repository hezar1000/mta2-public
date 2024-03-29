# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-08-22 22:14
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [("peer_review", "0002_reviewassignment_is_groundtruth")]

    operations = [
        migrations.AddField(
            model_name="reviewassignment",
            name="creation_date",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reviewassignment",
            name="modification_date",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
