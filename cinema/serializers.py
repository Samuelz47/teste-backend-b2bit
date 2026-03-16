"""
Cinema app serializers.

Exposure rules:
  - MovieSerializer / SessionSerializer / SeatSerializer → public read endpoints.
  - TicketSerializer → authenticated user endpoints; `locked_until` is intentionally
    omitted (internal lock data) but `purchased_at` and `status` are exposed.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Movie, Seat, Session, Ticket

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration (Caso 1).
    Uses `create_user` to guarantee proper password hashing.
    """

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
    """Read serializer for the Movie model."""

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
    """
    Read serializer for the Session model.
    Nests a lightweight representation of Movie to avoid extra client requests.
    """

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
    """Serializer exposing seat position and availability status."""

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
    """
    User-facing ticket serializer.
    `locked_until` is intentionally excluded — it is an internal implementation
    detail of the Redis seat-locking mechanism.
    """

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
