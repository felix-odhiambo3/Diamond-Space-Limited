
from collections import defaultdict

from django.db import migrations


def normalize_vehicle_registrations(apps, schema_editor):
    Vehicle = apps.get_model('vehicles', 'Vehicle')
    database = schema_editor.connection.alias

    vehicles = list(
        Vehicle.objects.using(database).all().only(
            'id',
            'registration_number'
        )
    )

    normalized_groups = defaultdict(list)
    normalized_values = {}

    # First inspect every record without changing the database.
    for vehicle in vehicles:
        original = vehicle.registration_number or ''
        normalized = ''.join(original.split()).upper()

        if not normalized:
            raise RuntimeError(
                f'Vehicle ID {vehicle.pk} has an empty registration number. '
                'No records were changed.'
            )

        if len(normalized) > 20:
            raise RuntimeError(
                f'Vehicle ID {vehicle.pk} would have a registration number '
                f'longer than 20 characters: {normalized!r}. '
                'No records were changed.'
            )

        normalized_groups[normalized].append(
            (vehicle.pk, original)
        )
        normalized_values[vehicle.pk] = normalized

    # Abort before updating anything if normalization creates duplicates.
    conflicts = {
        registration: records
        for registration, records in normalized_groups.items()
        if len(records) > 1
    }

    if conflicts:
        details = '\n'.join(
            f'{registration}: {records}'
            for registration, records in conflicts.items()
        )

        raise RuntimeError(
            'Vehicle registration normalization conflicts detected. '
            'No records were changed:\n' + details
        )

    # All records are safe to normalize.
    for vehicle in vehicles:
        normalized = normalized_values[vehicle.pk]

        if vehicle.registration_number != normalized:
            Vehicle.objects.using(database).filter(
                pk=vehicle.pk
            ).update(
                registration_number=normalized
            )


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0004_vehicle_category_and_make_model'),
    ]

    operations = [
        migrations.RunPython(
            normalize_vehicle_registrations,
            migrations.RunPython.noop
        ),
    ]
