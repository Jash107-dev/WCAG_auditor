from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_page_compliance_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='dismissed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='issue',
            name='dismissal_reason',
            field=models.CharField(
                blank=True, null=True, max_length=20,
                choices=[
                    ('false_positive', 'False Positive'),
                    ('not_applicable', 'Not Applicable'),
                    ('accepted_risk', 'Accepted Risk'),
                ]
            ),
        ),
        migrations.AddField(
            model_name='issue',
            name='dismissal_note',
            field=models.TextField(blank=True, null=True),
        ),
    ]
