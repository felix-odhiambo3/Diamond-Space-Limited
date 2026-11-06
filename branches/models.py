from django.db import models


class Branch(models.Model):

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)

    town = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Branches'

    def __str__(self):
        return f"{self.name} ({self.code})"