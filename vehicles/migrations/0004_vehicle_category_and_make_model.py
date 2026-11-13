from django.db import migrations, models
import django.db.models.deletion


def populate_vehicle_categories(apps, schema_editor):
    Vehicle = apps.get_model('vehicles', 'Vehicle')
    VehicleCategory = apps.get_model('vehicles', 'VehicleCategory')

    category_mapping = {
        'SALOON': 'Saloon',
        'SUV': 'SUV',
        'PICKUP': 'Pickup',
        'VAN': 'Van',
        'TRUCK': 'Truck',
        'MOTORCYCLE': 'Motorcycle',
        'OTHER': 'Other',
    }

    database = schema_editor.connection.alias

    vehicles = Vehicle.objects.using(database).all()

    for vehicle in vehicles.iterator():
        category_name = category_mapping.get(
            vehicle.vehicle_type,
            'Other'
        )

        category, created = (
            VehicleCategory.objects.using(database).get_or_create(
                name=category_name,
                defaults={'is_active': True},
            )
        )

        vehicle.category_id = category.pk
        vehicle.save(
            using=database,
            update_fields=['category'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0003_creditledgerentry_creditpaymentallocation_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VehicleCategory',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=80, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name_plural': 'Vehicle categories',
            },
        ),

        migrations.AddField(
            model_name='vehicle',
            name='make_model',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Vehicle make and model, for example Toyota or Nissan.',
                max_length=100,
            ),
            preserve_default=False,
        ),

        migrations.AddField(
            model_name='vehicle',
            name='category',
            field=models.ForeignKey(
                to='vehicles.vehiclecategory',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vehicles',
                null=True,
            ),
        ),

        migrations.RunPython(
            populate_vehicle_categories,
            migrations.RunPython.noop,
        ),

        migrations.AlterField(
            model_name='vehicle',
            name='category',
            field=models.ForeignKey(
                to='vehicles.vehiclecategory',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vehicles',
            ),
        ),
    ]