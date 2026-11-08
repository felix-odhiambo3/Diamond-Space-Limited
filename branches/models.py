
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Branch(models.Model):

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)

    town = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # GPS attendance configuration
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    attendance_radius = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Maximum permitted attendance distance in metres.",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Branches'

    def __str__(self):
        return f"{self.name} ({self.code})"
