from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='title',
            field=models.CharField(max_length=100, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='rule',
            name='category',
            field=models.CharField(max_length=50, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='rule',
            name='check_type',
            field=models.CharField(max_length=20, default='deterministic'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='rule',
            name='fix_suggestion',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
