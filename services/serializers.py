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

    def validate(self, attrs):
        category = attrs.get(
            'category',
            getattr(self.instance, 'category', None)
        )

        if category == Service.Category.DETAILING:
            attrs['requires_timer'] = False

        return attrs