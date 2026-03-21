import pytest
from unittest.mock import patch
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from cinema.models import Movie, Session, Seat, Ticket

User = get_user_model()

@pytest.fixture
def auth_client():
    user = User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user

@pytest.fixture
def movie(db):
    return Movie.objects.create(
        title="Inception", genre="Sci-Fi", duration_minutes=148, release_date="2010-07-16"
    )

@pytest.fixture
def session(db, movie):
    return Session.objects.create(
        movie=movie, room="IMAX", starts_at="2026-03-20T20:00:00Z", ends_at="2026-03-20T22:30:00Z",
        total_seats=10, available_seats=10, price="50.00"
    )

@pytest.fixture
def seat(db, session):
    return Seat.objects.create(session=session, row="A", number=1)

@pytest.mark.django_db
class TestReservationFlow:
    def test_reserve_seat_success(self, auth_client, seat):
        client, user = auth_client
        url = reverse("session-reserve-seat", args=[seat.session.id, seat.id])
        
        with patch("cinema.views.lock_seat", return_value=True) as mock_lock:
            resp = client.post(url)
            assert resp.status_code == status.HTTP_201_CREATED
            mock_lock.assert_called_once_with(seat.id, user.id)

    def test_reserve_seat_already_taken(self, auth_client, seat):
        client, user = auth_client
        seat.status = Seat.Status.PURCHASED
        seat.save()
        url = reverse("session-reserve-seat", args=[seat.session.id, seat.id])
        
        resp = client.post(url)
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "already taken" in resp.data["error"]

    def test_reserve_seat_lock_failed(self, auth_client, seat):
        client, user = auth_client
        url = reverse("session-reserve-seat", args=[seat.session.id, seat.id])
        
        with patch("cinema.views.lock_seat", return_value=False):
            resp = client.post(url)
            assert resp.status_code == status.HTTP_409_CONFLICT
            assert "currently being reserved" in resp.data["error"]

    def test_seat_map_shows_reserved_via_redis(self, auth_client, seat):
        client, _ = auth_client
        url = reverse("session-seats", args=[seat.session.id])
        
        with patch("cinema.views.get_locked_seat_ids", return_value={seat.id}):
            resp = client.get(url)
            assert resp.status_code == status.HTTP_200_OK
            seat_data = next(s for s in resp.data if s["id"] == seat.id)
            assert seat_data["status"] == "reserved"

    def test_checkout_success(self, auth_client, seat):
        client, user = auth_client
        url = reverse("session-checkout-seat", args=[seat.session.id, seat.id])
        
        mock_ticket = Ticket(user=user, session=seat.session, seat=seat, status=Ticket.Status.PURCHASED)
        
        with patch("cinema.views.checkout_seat", return_value=mock_ticket) as mock_checkout:
            resp = client.post(url)
            assert resp.status_code == status.HTTP_201_CREATED
            assert resp.data["status"] == "purchased"
            mock_checkout.assert_called_once_with(seat, user)

    def test_checkout_no_auth(self, seat):
        client = APIClient()
        url = reverse("session-checkout-seat", args=[seat.session.id, seat.id])
        resp = client.post(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
