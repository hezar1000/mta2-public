# Generated by Django 2.1.15 on 2021-01-26 00:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peer_review', '0015_reviewassignment_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewcontent',
            name='component_grade',
            field=models.FloatField(blank=True, db_column='component_wise_grade', default=0, verbose_name='component_wise_grade'),
        ),
    ]
