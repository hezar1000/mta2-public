# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-09-26 17:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_assignment", "0007_auto_20180905_2051")]

    operations = [
        migrations.AlterField(
            model_name="assignmentquestion",
            name="description",
            field=models.CharField(
                max_length=2096, verbose_name="Question Description"
            ),
        )
    ]