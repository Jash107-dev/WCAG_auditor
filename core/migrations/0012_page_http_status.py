from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_project_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='page',
            name='http_status',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
