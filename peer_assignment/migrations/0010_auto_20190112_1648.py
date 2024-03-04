# Generated by Django 2.1.5 on 2019-01-13 00:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("peer_assignment", "0009_auto_20181101_1403")]

    operations = [
        migrations.AlterField(
            model_name="assignment",
            name="browsable",
            field=models.BooleanField(
                blank=True,
                db_column="visible",
                default=False,
                verbose_name="Visible to students",
            ),
        ),
        migrations.AlterField(
            model_name="assignmentquestion",
            name="evaluation_rubric",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="evaluated_question",
                to="peer_review.Rubric",
            ),
        ),
        migrations.AlterField(
            model_name="assignmentquestion",
            name="rubric",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="peer_review.Rubric",
            ),
        ),
    ]