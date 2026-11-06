from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        SUPERVISOR = 'SUPERVISOR', 'Supervisor'
        ACCOUNTS = 'ACCOUNTS', 'Accounts'
        CLEANER = 'CLEANER', 'Cleaner'
        DETAILER = 'DETAILER', 'Detailer'

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLEANER,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"