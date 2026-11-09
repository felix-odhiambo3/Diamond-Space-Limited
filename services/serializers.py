
from rest_framework import serializers

from .models import Service


class ServiceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'code',
            'category',
            'description',
            'price',
            'duration_minutes',
            'requires_timer',
            'is_active',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Service price cannot be negative."
            )

        return value

    def validate_duration_minutes(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "Service duration must be greater than zero."
            )

        return value

    def validate(self, attrs):
        category = attrs.get(
            'category',
            getattr(self.instance, 'category', None)
        )

        if category == Service.Category.DETAILING:
            attrs['requires_timer'] = False

        return attrs
