import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from cinema.models import Movie, Session, Seat, Ticket

User = get_user_model()

@pytest.fixture
def user_a(db):
    return User.objects.create_user(username="user_a", password="password123")

@pytest.fixture
def user_b(db):
    return User.objects.create_user(username="user_b", password="password123")

@pytest.fixture
def auth_client_a(user_a):
    client = APIClient()
    client.force_authenticate(user=user_a)
    return client

@pytest.fixture
def movie(db):
    return Movie.objects.create(
        title="Test Movie", genre="Action", duration_minutes=120, release_date="2024-01-01"
    )

@pytest.fixture
def session(db, movie):
    return Session.objects.create(
        movie=movie, room="Room 1", starts_at="2026-03-21T20:00:00Z", ends_at="2026-03-21T22:00:00Z",
        total_seats=10, available_seats=10, price="30.00"
    )

@pytest.fixture
def tickets_a(user_a, session):
    seat1 = Seat.objects.create(session=session, row="A", number=1)
    seat2 = Seat.objects.create(session=session, row="A", number=2)
    t1 = Ticket.objects.create(user=user_a, session=session, seat=seat1, status=Ticket.Status.PURCHASED)
    t2 = Ticket.objects.create(user=user_a, session=session, seat=seat2, status=Ticket.Status.PURCHASED)
    return [t1, t2]

@pytest.fixture
def ticket_b(user_b, session):
    seat3 = Seat.objects.create(session=session, row="B", number=1)
    return Ticket.objects.create(user=user_b, session=session, seat=seat3, status=Ticket.Status.PURCHASED)

@pytest.mark.django_db
class TestTicketList:
    LIST_URL = reverse("ticket-list")

    def test_list_own_tickets_success(self, auth_client_a, tickets_a, ticket_b):
        resp = auth_client_a.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data
        assert len(resp.data["results"]) == 2
        ticket_ids = [t["id"] for t in resp.data["results"]]
        assert ticket_b.id not in ticket_ids

    def test_list_tickets_unauthenticated(self, db):
        client = APIClient()
        resp = client.get(self.LIST_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_own_ticket(self, auth_client_a, tickets_a):
        ticket = tickets_a[0]
        url = reverse("ticket-detail", args=[ticket.id])
        resp = auth_client_a.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == ticket.id

    def test_cannot_retrieve_others_ticket(self, auth_client_a, ticket_b):
        url = reverse("ticket-detail", args=[ticket_b.id])
        resp = auth_client_a.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
