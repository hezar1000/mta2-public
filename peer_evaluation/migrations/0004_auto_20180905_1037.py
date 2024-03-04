# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-09-05 17:37
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("peer_evaluation", "0003_auto_20180903_1222")]

    operations = [
        migrations.AlterField(
            model_name="evaluationcontent",
            name="evaluation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contents",
                to="peer_evaluation.EvaluationAssignment",
            ),
        )
    ]