from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from cinema.models import Movie, Seat, Session

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def movie(db) -> Movie:
    return Movie.objects.create(
        title="The Matrix",
        genre="Sci-Fi",
        duration_minutes=136,
        release_date="1999-03-31",
        is_active=True,
    )


@pytest.fixture
def inactive_movie(db) -> Movie:
    return Movie.objects.create(
        title="Old Film",
        genre="Drama",
        duration_minutes=90,
        release_date="1980-01-01",
        is_active=False,
    )


@pytest.fixture
def session(db, movie: Movie) -> Session:
    starts = timezone.now() + timezone.timedelta(hours=2)
    ends = starts + timezone.timedelta(hours=movie.duration_minutes // 60 + 1)
    return Session.objects.create(
        movie=movie,
        room="Sala VIP",
        starts_at=starts,
        ends_at=ends,
        total_seats=5,
        available_seats=5,
        price="35.00",
    )


@pytest.fixture
def seats(db, session: Session) -> list[Seat]:
    created = []
    for row in ("A", "B"):
        for num in (1, 2, 3):
            s = Seat.objects.create(session=session, row=row, number=num)
            created.append(s)
    reserved = created[0]
    reserved.status = Seat.Status.RESERVED
    reserved.save()
    return created


@pytest.mark.django_db
class TestUserRegistration:
    REGISTER_URL = reverse("user-register")

    def test_register_success(self, api_client: APIClient) -> None:
        payload = {
            "username": "neo",
            "email": "neo@matrix.com",
            "password": "test_password_123",
        }
        resp = api_client.post(self.REGISTER_URL, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert "id" in resp.data
        assert resp.data["username"] == "neo"
        assert "password" not in resp.data

    def test_password_is_hashed(self, api_client: APIClient) -> None:
        api_client.post(
            self.REGISTER_URL,
            {"username": "trinity", "email": "t@m.com", "password": "test_password_456"},
        )
        user = User.objects.get(username="trinity")
        assert user.check_password("test_password_456")
        assert user.password != "test_password_456"

    def test_short_password_rejected(self, api_client: APIClient) -> None:
        resp = api_client.post(
            self.REGISTER_URL,
            {"username": "morph", "email": "m@m.com", "password": "short"},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_username(self, api_client: APIClient, db) -> None:
        User.objects.create_user(username="agent", password="secure_test_pass_1")
        resp = api_client.post(
            self.REGISTER_URL,
            {"username": "agent", "email": "a@m.com", "password": "secure_test_pass_2"},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


class TestMovieViewSet:
    LIST_URL = reverse("movie-list")

    def test_list_movies(self, api_client: APIClient, movie: Movie) -> None:
        resp = api_client.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["title"] == "The Matrix"

    def test_inactive_movies_excluded(
        self, api_client: APIClient, movie: Movie, inactive_movie: Movie
    ) -> None:
        resp = api_client.get(self.LIST_URL)
        titles = [m["title"] for m in resp.data["results"]]
        assert "Old Film" not in titles

    def test_detail(self, api_client: APIClient, movie: Movie) -> None:
        url = reverse("movie-detail", args=[movie.pk])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["title"] == "The Matrix"

    def test_no_write_operations(self, api_client: APIClient, movie: Movie) -> None:
        resp = api_client.post(self.LIST_URL, {"title": "Hack"})
        assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestSessionViewSet:
    LIST_URL = reverse("session-list")

    def test_list_sessions(self, api_client: APIClient, session: Session) -> None:
        resp = api_client.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data
        assert len(resp.data["results"]) == 1

    def test_nested_movie(self, api_client: APIClient, session: Session) -> None:
        resp = api_client.get(self.LIST_URL)
        movie_data = resp.data["results"][0]["movie"]
        assert isinstance(movie_data, dict)
        assert movie_data["title"] == "The Matrix"

    def test_detail(self, api_client: APIClient, session: Session) -> None:
        url = reverse("session-detail", args=[session.pk])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK


class TestSeatMap:
    def test_seat_map_returns_all_seats(
        self, api_client: APIClient, session: Session, seats: list[Seat]
    ) -> None:
        url = reverse("session-seats", args=[session.pk])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 6

    def test_seat_map_includes_status(
        self, api_client: APIClient, session: Session, seats: list[Seat]
    ) -> None:
        url = reverse("session-seats", args=[session.pk])
        resp = api_client.get(url)
        statuses = {s["status"] for s in resp.data}
        assert "available" in statuses
        assert "reserved" in statuses

    def test_seat_map_ordering(
        self, api_client: APIClient, session: Session, seats: list[Seat]
    ) -> None:
        url = reverse("session-seats", args=[session.pk])
        resp = api_client.get(url)
        rows = [s["row"] for s in resp.data]
        numbers = [s["number"] for s in resp.data]
        assert rows == sorted(rows)
        a_numbers = [s["number"] for s in resp.data if s["row"] == "A"]
        assert a_numbers == sorted(a_numbers)

    def test_seat_map_fields(
        self, api_client: APIClient, session: Session, seats: list[Seat]
    ) -> None:
        url = reverse("session-seats", args=[session.pk])
        resp = api_client.get(url)
        first_seat = resp.data[0]
        assert "id" in first_seat
        assert "row" in first_seat
        assert "number" in first_seat
        assert "status" in first_seat

    def test_seat_map_invalid_session(self, api_client: APIClient, db) -> None:
        url = reverse("session-seats", args=[99999])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
