from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("summaries", "0005_alter_summary_options_alter_document_uploaded_file_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="source_type",
            field=models.CharField(
                choices=[("text", "Văn bản"), ("file", "Tệp"), ("url", "URL")],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="summary",
            name="document",
            field=models.ForeignKey(
                db_index=True,
                on_delete=models.CASCADE,
                related_name="summaries",
                to="summaries.document",
            ),
        ),
        migrations.AlterField(
            model_name="summarysentence",
            name="summary",
            field=models.ForeignKey(
                db_index=True,
                on_delete=models.CASCADE,
                related_name="sentences",
                to="summaries.summary",
            ),
        ),
    ]
