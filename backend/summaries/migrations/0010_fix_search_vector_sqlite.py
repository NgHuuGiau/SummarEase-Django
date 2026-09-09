# Generated manually for SQLite compatibility
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('summaries', '0009_summary_search_vector_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='summary',
            name='search_vector',
            field=models.TextField(blank=True, editable=False, null=True),
        ),
        migrations.RemoveIndex(
            model_name='summary',
            name='summaries_s_search__c92837_idx',
        ),
    ]