# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-09-06 02:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_assignment", "0005_assignmentquestion_evaluation_rubric")]

    operations = [
        migrations.AddField(
            model_name="assignmentsubmission",
            name="attempts",
            field=models.PositiveIntegerField(blank=True, default=1),
        )
    ]