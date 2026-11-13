from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visits', '0002_serviceassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='visit',
            name='plastic_mat_count',
            field=models.PositiveIntegerField(default=0),
        ),

        migrations.AddField(
            model_name='visit',
            name='woolen_mat_count',
            field=models.PositiveIntegerField(default=0),
        ),

        migrations.RenameField(
            model_name='visit',
            old_name='notes',
            new_name='comment',
        ),
    ]