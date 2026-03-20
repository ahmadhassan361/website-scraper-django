# Generated migration for adding unmatched_products field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0015_merge_20260315_2301'),
    ]

    operations = [
        migrations.AddField(
            model_name='websiteimportlog',
            name='unmatched_products',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text='List of products from import file that could not be matched in database'
            ),
        ),
    ]
