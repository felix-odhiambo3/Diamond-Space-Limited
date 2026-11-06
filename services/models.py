from django.db import models


class Service(models.Model):

    class Category(models.TextChoices):
        CAR_WASH = 'CAR_WASH', 'Car Wash'
        DETAILING = 'DETAILING', 'Detailing'

    name = models.CharField(max_length=150)

    code = models.CharField(
        max_length=30,
        unique=True
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices
    )

    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    requires_timer = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} - KES {self.price}"

    def save(self, *args, **kwargs):
        if self.category == self.Category.DETAILING:
            self.requires_timer = False

        super().save(*args, **kwargs)