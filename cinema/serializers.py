from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Movie, Seat, Session, Ticket

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {
            "email": {"required": True},
        }

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = [
            "id",
            "title",
            "genre",
            "duration_minutes",
            "release_date",
            "synopsis",
            "poster_url",
            "is_active",
        ]
        read_only_fields = fields


class SessionSerializer(serializers.ModelSerializer):
    movie = MovieSerializer(read_only=True)
    movie_id = serializers.PrimaryKeyRelatedField(
        queryset=Movie.objects.filter(is_active=True),
        source="movie",
        write_only=True,
    )

    class Meta:
        model = Session
        fields = [
            "id",
            "movie",
            "movie_id",
            "room",
            "starts_at",
            "ends_at",
            "total_seats",
            "available_seats",
            "price",
        ]
        read_only_fields = ["available_seats"]


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = [
            "id",
            "session",
            "row",
            "number",
            "status",
        ]
        read_only_fields = ["status"]


class TicketSerializer(serializers.ModelSerializer):
    seat = SeatSerializer(read_only=True)
    session = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "session",
            "seat",
            "status",
            "purchased_at",
            "created_at",
        ]
        read_only_fields = fields
