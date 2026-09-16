# Generated manually for SQLite compatibility
from django.db import migrations, models

SEARCH_VECTOR_INDEX = 'summaries_s_search__c92837_idx'


def remove_search_vector_index_if_present(apps, schema_editor):
    """The index exists only on PostgreSQL after the backend-aware 0009 migration."""
    if schema_editor.connection.vendor != "postgresql":
        return

    Summary = apps.get_model("summaries", "Summary")
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, Summary._meta.db_table
        )
    if SEARCH_VECTOR_INDEX in constraints:
        schema_editor.remove_index(
            Summary,
            models.Index(fields=["search_vector"], name=SEARCH_VECTOR_INDEX),
        )


def restore_search_vector_index_if_postgresql(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        Summary = apps.get_model("summaries", "Summary")
        schema_editor.add_index(
            Summary,
            models.Index(fields=["search_vector"], name=SEARCH_VECTOR_INDEX),
        )


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
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    remove_search_vector_index_if_present,
                    restore_search_vector_index_if_postgresql,
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="summary",
                    name=SEARCH_VECTOR_INDEX,
                ),
            ],
        ),
    ]
