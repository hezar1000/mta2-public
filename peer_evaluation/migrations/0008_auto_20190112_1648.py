# Generated by Django 2.1.5 on 2019-01-13 00:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peer_evaluation", "0007_auto_20180910_2312")]

    operations = [
        migrations.AlterField(
            model_name="evaluationassignment",
            name="submitted",
            field=models.BooleanField(blank=True, db_index=True, default=False),
        )
    ]
