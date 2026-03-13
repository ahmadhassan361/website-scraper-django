# Generated migration file

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0012_alter_product_category_alter_product_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='googlesheetlinks',
            name='sheet_file_id',
            field=models.CharField(blank=True, max_length=255, null=True, help_text='Google Drive file ID for reusing sheet'),
        ),
    ]
