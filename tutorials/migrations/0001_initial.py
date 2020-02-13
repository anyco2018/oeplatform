# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2020-02-13 22:09
from __future__ import unicode_literals

from django.db import migrations, models
import martor.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Tutorial',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(blank=True, choices=[('io', 'I/O'), ('intro', 'Introduction')], max_length=15)),
                ('title', models.TextField()),
                ('html', models.TextField()),
                ('markdown', martor.models.MartorField()),
                ('level', models.IntegerField(choices=[(1, 'Beginners'), (2, 'Intermediates'), (3, 'Advanced')], null=True)),
            ],
        ),
    ]
