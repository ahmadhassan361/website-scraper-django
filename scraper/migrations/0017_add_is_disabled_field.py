# Generated migration for adding is_disabled field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0016_add_unmatched_products'),
    ]

    operations = [
        migrations.AddField(
            model_name='productsyncstatus',
            name='is_disabled',
            field=models.BooleanField(
                default=False,
                help_text='If true, this product will be excluded from matching, exporting, and normal display'
            ),
        ),
        migrations.AddField(
            model_name='productsyncstatus',
            name='disabled_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='When this product was disabled'
            ),
        ),
        migrations.AddField(
            model_name='productsyncstatus',
            name='disabled_reason',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Optional reason for disabling this product'
            ),
        ),
    ]
