# Generated by Django 2.1.15 on 2021-01-22 03:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_assignment', '0017_auto_20210121_1908'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignmentsubmission',
            name='spotchecking_priority',
            field=models.FloatField(db_column='spotcheckingpriority', default=20, verbose_name='Spotchecking Priority'),
        ),
    ]
