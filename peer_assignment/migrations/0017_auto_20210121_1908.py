# Generated by Django 2.1.15 on 2021-01-22 03:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_assignment', '0016_assignmentsubmission_spotchecking_priority'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignmentsubmission',
            name='spotchecking_priority',
            field=models.FloatField(db_column='spotcheckingpriority', default=10, verbose_name='Spotchecking Priority'),
        ),
    ]