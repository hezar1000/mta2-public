# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-08-10 17:30
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("peer_course", "0001_initial"),
        ("peer_assignment", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssignmentWithReviews",
            fields=[
                (
                    "assignment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="peer_assignment.Assignment",
                    ),
                ),
                (
                    "student_review_deadline_default",
                    models.DateTimeField(
                        db_column="student_review_deadline_default",
                        null=True,
                        verbose_name="Default Deadline for Student Reviews",
                    ),
                ),
                (
                    "ta_review_deadline_default",
                    models.DateTimeField(
                        db_column="ta_review_deadline_default",
                        null=True,
                        verbose_name="Default Deadline for TA Reviews",
                    ),
                ),
            ],
            options={"db_table": "assignment_with_reviews"},
        ),
        migrations.CreateModel(
            name="ReviewAssignment",
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
                    "nopublicuse",
                    models.BooleanField(
                        db_column="noPublicUse",
                        default=False,
                        verbose_name="Check this if you do not want your review submission to be used anonymously in public.",
                    ),
                ),
                (
                    "grader",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="peer_course.CourseMember",
                    ),
                ),
                (
                    "submission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="peer_assignment.AssignmentSubmission",
                    ),
                ),
            ],
            options={"db_table": "review_assignment"},
        ),
        migrations.CreateModel(
            name="ReviewContent",
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
                ("reason", models.TextField(blank=True, default="")),
            ],
            options={"db_table": "review_content"},
        ),
        migrations.CreateModel(
            name="ReviewContentFile",
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
                    "attachment",
                    models.FileField(
                        db_column="file",
                        upload_to="",
                        verbose_name="Review Content File",
                    ),
                ),
                (
                    "review_content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="peer_review.ReviewContent",
                    ),
                ),
            ],
            options={"db_table": "review_content_file"},
        ),
        migrations.CreateModel(
            name="Rubric",
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
                    "name",
                    models.CharField(
                        db_column="name", max_length=128, verbose_name="Display Name"
                    ),
                ),
            ],
            options={"db_table": "rubric"},
        ),
        migrations.CreateModel(
            name="RubricQuestion",
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
                    "title",
                    models.CharField(
                        db_column="question_title",
                        max_length=128,
                        verbose_name="Question Title",
                    ),
                ),
                (
                    "text",
                    models.CharField(
                        db_column="question_text",
                        max_length=1000,
                        verbose_name="Question Description",
                    ),
                ),
                (
                    "min_reason_length",
                    models.PositiveIntegerField(
                        default=20, verbose_name="Min Length of Reasoning field"
                    ),
                ),
                (
                    "max_reason_length",
                    models.PositiveIntegerField(
                        default=500, verbose_name="Max Length of Reasoning field"
                    ),
                ),
            ],
            options={"db_table": "rubric_question"},
        ),
        migrations.CreateModel(
            name="RubricQuestionMultipleChoiceItem",
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
                    "text",
                    models.CharField(
                        db_column="item_text",
                        max_length=1000,
                        verbose_name="Item Description",
                    ),
                ),
                (
                    "marks",
                    models.IntegerField(
                        blank=True,
                        db_column="item_marks",
                        default=0,
                        verbose_name="Number of Marks",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="peer_review.RubricQuestion",
                    ),
                ),
            ],
            options={"db_table": "rubric_question_multiple_choice_item"},
        ),
        migrations.CreateModel(
            name="ValidationRule",
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
                    "rule_type",
                    models.CharField(
                        choices=[
                            ("MAXCHAR", "Maximum number of characters"),
                            ("MINCHAR", "Minimum number of characters"),
                        ],
                        db_column="rule_type",
                        default="NONE",
                        max_length=128,
                        verbose_name="Rule Type",
                    ),
                ),
                (
                    "rule_content",
                    models.TextField(
                        db_column="rule_content", verbose_name="Rule Content"
                    ),
                ),
                (
                    "rubric_question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="peer_review.RubricQuestion",
                    ),
                ),
            ],
            options={"db_table": "rubric_validation_rule"},
        ),
        migrations.AddField(
            model_name="rubric",
            name="questions",
            field=models.ManyToManyField(to="peer_review.RubricQuestion"),
        ),
        migrations.AddField(
            model_name="reviewcontent",
            name="choice",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="peer_review.RubricQuestionMultipleChoiceItem",
            ),
        ),
        migrations.AddField(
            model_name="reviewcontent",
            name="review_assignment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="peer_review.ReviewAssignment",
            ),
        ),
        migrations.AddField(
            model_name="reviewcontent",
            name="submission_component",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="peer_assignment.SubmissionComponent",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="reviewassignment", unique_together=set([("submission", "grader")])
        ),
    ]
