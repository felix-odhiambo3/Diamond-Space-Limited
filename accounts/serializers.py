from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        identifier = attrs.get(self.username_field)

        # Allow login using email address.
        if identifier and '@' in identifier:
            user = User.objects.filter(
                email__iexact=identifier
            ).first()

            if user:
                attrs[self.username_field] = user.get_username()

        data = super().validate(attrs)

        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
        }

        return data


class UserCreateSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'role',
        ]
        read_only_fields = ['id']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

    def validate_role(self, value):
        request = self.context.get('request')

        if (
            value == User.Role.OWNER
            and request
            and request.user.is_authenticated
            and not (
                request.user.is_superuser
                or request.user.role == User.Role.OWNER
            )
        ):
            raise serializers.ValidationError(
                "Only an Owner or superuser can assign the Owner role."
            )

        return value

    def create(self, validated_data):
        password = validated_data.pop('password')

        return User.objects.create_user(
            password=password,
            **validated_data
        )


class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
        ]
        read_only_fields = ['id', 'username']

    def validate_email(self, value):
        user = self.instance

        if User.objects.filter(
            email__iexact=value
        ).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

    def validate(self, attrs):
        request = self.context.get('request')
        actor = request.user if request else None
        target = self.instance

        if not actor or not actor.is_authenticated:
            raise serializers.ValidationError(
                "An authenticated user is required."
            )

        can_manage_owner = (
            actor.is_superuser
            or actor.role == User.Role.OWNER
        )

        # Admins cannot edit an existing Owner account.
        if target.role == User.Role.OWNER and not can_manage_owner:
            raise serializers.ValidationError(
                "Only an Owner or superuser can modify an Owner account."
            )

        # Admins cannot promote themselves or another user to Owner.
        if (
            attrs.get('role') == User.Role.OWNER
            and not can_manage_owner
        ):
            raise serializers.ValidationError({
                'role': (
                    "Only an Owner or superuser can assign the Owner role."
                )
            })

        return attrs


class UserListSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'date_joined',
        ]