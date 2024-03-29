# Generated by Django 2.1.5 on 2019-01-13 04:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_assignment", "0010_auto_20190112_1648")]

    operations = [
        migrations.AlterField(
            model_name="assignment",
            name="browsable",
            field=models.BooleanField(
                blank=True,
                db_column="visible",
                db_index=True,
                default=False,
                verbose_name="Visible to students",
            ),
        ),
        migrations.AlterField(
            model_name="assignment",
            name="deadline",
            field=models.DateTimeField(
                blank=True,
                db_column="deadline",
                db_index=True,
                default=None,
                null=True,
                verbose_name="Deadline",
            ),
        ),
        migrations.AlterField(
            model_name="assignmentquestion",
            name="category",
            field=models.CharField(
                choices=[
                    ("NONE", "--------"),
                    ("MULT", "Multiple Choice"),
                    ("TEXT", "Text"),
                    ("FILE", "File"),
                ],
                db_column="question_type",
                db_index=True,
                default="NONE",
                max_length=128,
                verbose_name="Question Type",
            ),
        ),
        migrations.AlterField(
            model_name="assignmentsubmission",
            name="calibration_id",
            field=models.IntegerField(
                blank=True,
                db_column="calibration_id",
                db_index=True,
                default=0,
                verbose_name="calibration_id",
            ),
        ),
        migrations.AlterField(
            model_name="assignmentsubmission",
            name="time_submitted",
            field=models.DateTimeField(
                auto_now_add=True, db_index=True, verbose_name="Time submitted"
            ),
        ),
    ]
