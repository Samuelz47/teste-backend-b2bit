import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from cinema.models import Seat, Ticket, Session, Movie
from cinema.services.reservation import lock_seat, checkout_seat, get_locked_seat_ids

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="password")

@pytest.fixture
def movie(db):
    return Movie.objects.create(title="Movie", genre="Action", duration_minutes=100, release_date="2024-01-01")

@pytest.fixture
def session(db, movie):
    return Session.objects.create(
        movie=movie, room="Room", starts_at="2026-03-21T20:00:00Z", ends_at="2026-03-21T22:00:00Z",
        total_seats=10, available_seats=10, price="10.00"
    )

@pytest.fixture
def seat(db, session):
    return Seat.objects.create(session=session, row="A", number=1)

@pytest.mark.django_db
class TestReservationService:
    @patch("cinema.services.reservation.get_redis_connection")
    def test_lock_seat_redis_logic(self, mock_get_con, seat, user):
        mock_con = MagicMock()
        mock_get_con.return_value = mock_con
        mock_con.set.return_value = True
        
        success = lock_seat(seat.id, user.id)
        
        assert success is True
        mock_con.set.assert_called_once_with(f"seat_lock:{seat.id}", user.id, nx=True, ex=600)

    @patch("cinema.services.reservation.get_redis_connection")
    def test_get_locked_seat_ids(self, mock_get_con):
        mock_con = MagicMock()
        mock_get_con.return_value = mock_con
        mock_con.mget.return_value = [b"10", b"11", None]
        
        locked_ids = get_locked_seat_ids([1, 2, 3])
        
        assert locked_ids == {1, 2}
        mock_con.mget.assert_called_once_with(["seat_lock:1", "seat_lock:2", "seat_lock:3"])

    @patch("cinema.services.reservation.get_redis_connection")
    def test_checkout_seat_success(self, mock_get_con, seat, user):
        mock_con = MagicMock()
        mock_get_con.return_value = mock_con
        mock_con.get.return_value = str(user.id).encode()
        
        ticket = checkout_seat(seat, user)
        
        assert ticket.status == Ticket.Status.PURCHASED
        assert ticket.user == user
        seat.refresh_from_db()
        assert seat.status == Seat.Status.PURCHASED
        mock_con.delete.assert_called_once_with(f"seat_lock:{seat.id}")

    @patch("cinema.services.reservation.get_redis_connection")
    def test_checkout_seat_no_lock(self, mock_get_con, seat, user):
        mock_con = MagicMock()
        mock_get_con.return_value = mock_con
        mock_con.get.return_value = None
        
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with pytest.raises(DRFValidationError) as excinfo:
            checkout_seat(seat, user)
        
        assert "expired" in str(excinfo.value).lower()

    @patch("cinema.services.reservation.get_redis_connection")
    def test_checkout_seat_wrong_user(self, mock_get_con, seat, user):
        mock_con = MagicMock()
        mock_get_con.return_value = mock_con
        mock_con.get.return_value = b"999"
        
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with pytest.raises(DRFValidationError) as excinfo:
            checkout_seat(seat, user)
        
        assert "locked by another user" in str(excinfo.value).lower()
