# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-08-10 17:30
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "displayname",
                    models.CharField(
                        db_column="display_name",
                        max_length=128,
                        verbose_name="Display Name",
                    ),
                ),
                (
                    "browsable",
                    models.BooleanField(
                        db_column="browsable", verbose_name="Visible to Students?"
                    ),
                ),
                (
                    "archived",
                    models.BooleanField(db_column="archived", verbose_name="Archived?"),
                ),
                (
                    "stucode",
                    models.CharField(
                        db_column="student_enroll_code",
                        max_length=128,
                        null=True,
                        verbose_name="Student Enroll Code",
                    ),
                ),
                (
                    "tascode",
                    models.CharField(
                        db_column="ta_enroll_code",
                        max_length=128,
                        null=True,
                        verbose_name="TA Enroll Code",
                    ),
                ),
                (
                    "instructor_code",
                    models.CharField(
                        db_column="instructor_enroll_code",
                        max_length=128,
                        null=True,
                        verbose_name="Instructor Enroll Code",
                    ),
                ),
                ("total_late_units", models.IntegerField(blank=True, default=6)),
            ],
            options={"db_table": "course"},
        ),
        migrations.CreateModel(
            name="CourseMember",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        db_column="role", max_length=128, verbose_name="User Type"
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="peer_course.Course",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "course_member"},
        ),
        migrations.AlterUniqueTogether(
            name="coursemember", unique_together=set([("course", "user")])
        ),
    ]