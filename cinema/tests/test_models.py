"""
Unit tests for the cinema app models.

Uses pytest-django with an in-memory SQLite-style DB automatically configured
by pytest-django. Tests focus on:
  - Model creation with valid data
  - Seat.Status choices
  - unique_together constraints on Seat and Ticket
  - Serializer output (no locked_until leak, correct nesting)
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from cinema.models import Movie, Seat, Session, Ticket
from cinema.serializers import (
    MovieSerializer,
    SeatSerializer,
    SessionSerializer,
    TicketSerializer,
)

User = get_user_model()


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def movie(db) -> Movie:
    return Movie.objects.create(
        title="Inception",
        genre="Sci-Fi",
        duration_minutes=148,
        release_date="2010-07-16",
        synopsis="A thief who steals corporate secrets.",
        is_active=True,
    )


@pytest.fixture
def session(db, movie: Movie) -> Session:
    starts = timezone.now() + timezone.timedelta(hours=2)
    ends = starts + timezone.timedelta(hours=2, minutes=28)
    return Session.objects.create(
        movie=movie,
        room="Sala 1",
        starts_at=starts,
        ends_at=ends,
        total_seats=100,
        available_seats=100,
        price="25.00",
    )


@pytest.fixture
def seat(db, session: Session) -> Seat:
    return Seat.objects.create(session=session, row="A", number=1)


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="tester", password="strongpass123")


@pytest.fixture
def locked_ticket(db, user: User, session: Session, seat: Seat) -> Ticket:
    return Ticket.objects.create(
        user=user,
        session=session,
        seat=seat,
        locked_until=timezone.now() + timezone.timedelta(minutes=10),
    )


# ── Model tests ───────────────────────────────────────────────────────────────
class TestMovie:
    def test_create_movie(self, movie: Movie) -> None:
        assert movie.pk is not None
        assert movie.title == "Inception"
        assert movie.is_active is True

    def test_str(self, movie: Movie) -> None:
        assert str(movie) == "Inception"


class TestSession:
    def test_create_session(self, session: Session, movie: Movie) -> None:
        assert session.pk is not None
        assert session.movie == movie
        assert session.available_seats == 100

    def test_str_contains_movie_title(self, session: Session) -> None:
        assert "Inception" in str(session)


class TestSeat:
    def test_default_status_is_available(self, seat: Seat) -> None:
        assert seat.status == Seat.Status.AVAILABLE

    def test_status_choices(self, seat: Seat) -> None:
        valid_statuses = {choice.value for choice in Seat.Status}
        assert seat.status in valid_statuses

    def test_unique_together_raises_on_duplicate(
        self, db, session: Session, seat: Seat
    ) -> None:
        with pytest.raises(IntegrityError):
            Seat.objects.create(session=session, row="A", number=1)

    def test_str(self, seat: Seat) -> None:
        assert "A1" in str(seat)
        assert "Available" in str(seat)


class TestTicket:
    def test_create_ticket(self, locked_ticket: Ticket) -> None:
        assert locked_ticket.pk is not None
        assert locked_ticket.status == Ticket.Status.LOCKED

    def test_unique_together_raises_on_duplicate(
        self, db, user: User, session: Session, seat: Seat, locked_ticket: Ticket
    ) -> None:
        with pytest.raises(IntegrityError):
            Ticket.objects.create(user=user, session=session, seat=seat)


# ── Serializer tests ──────────────────────────────────────────────────────────
class TestMovieSerializer:
    def test_fields_present(self, movie: Movie) -> None:
        data = MovieSerializer(movie).data
        assert "title" in data
        assert "genre" in data
        assert "is_active" in data

    def test_no_extra_internal_fields(self, movie: Movie) -> None:
        data = MovieSerializer(movie).data
        assert "created_at" not in data
        assert "updated_at" not in data


class TestSessionSerializer:
    def test_nested_movie(self, session: Session) -> None:
        data = SessionSerializer(session).data
        assert isinstance(data["movie"], dict)
        assert data["movie"]["title"] == "Inception"

    def test_movie_id_write_only(self, session: Session) -> None:
        data = SessionSerializer(session).data
        assert "movie_id" not in data


class TestTicketSerializer:
    def test_locked_until_not_exposed(self, locked_ticket: Ticket) -> None:
        data = TicketSerializer(locked_ticket).data
        assert "locked_until" not in data

    def test_expected_fields(self, locked_ticket: Ticket) -> None:
        data = TicketSerializer(locked_ticket).data
        for field in ("id", "session", "seat", "status", "purchased_at", "created_at"):
            assert field in data
