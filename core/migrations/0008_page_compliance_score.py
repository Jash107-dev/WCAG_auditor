from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_llm_stop_requested'),
    ]

    operations = [
        migrations.AddField(
            model_name='page',
            name='compliance_score',
            field=models.IntegerField(default=100),
        ),
    ]
