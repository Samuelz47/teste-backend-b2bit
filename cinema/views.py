"""
Cinema app views.

Casos implementados:
  1. Auth — User registration (POST /api/register/)
  2. Filmes — ReadOnlyModelViewSet (GET /api/movies/)
  3. Sessões — ReadOnlyModelViewSet (GET /api/sessions/)
  4. Mapa de Assentos — @action em SessionViewSet (GET /api/sessions/<id>/seats/)

Design decisions:
  - Redis cache (TC.3.2) via `@method_decorator(cache_page(...))` nos `list` de
    Movies e Sessions. Cache key é por URL (default do cache_page), TTL = 5 min.
  - Movies e Sessions são endpoints públicos (AllowAny), já que são dados de
    catálogo. O registro é público também. Ticket views futuras exigirão auth.
  - O seat map é público (sem auth) para que o frontend mostre disponibilidade
    antes do login.
"""
from __future__ import annotations

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Movie, Seat, Session
from .serializers import (
    MovieSerializer,
    SeatSerializer,
    SessionSerializer,
    TicketSerializer,
    UserRegistrationSerializer,
)
from .services.reservation import checkout_seat, get_locked_seat_ids, lock_seat

# Cache TTL for high-read endpoints (5 minutes)
CACHE_TTL_SECONDS: int = 60 * 5


# ── Caso 1: Auth ──────────────────────────────────────────────────────────────
@extend_schema(tags=["auth"])
class UserRegistrationView(generics.CreateAPIView):
    """
    POST /api/register/

    Creates a new user account. Password is hashed automatically via
    ``User.objects.create_user``.
    """

    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


# ── Caso 2: Filmes ────────────────────────────────────────────────────────────
@extend_schema_view(
    list=extend_schema(tags=["movies"], summary="List all active movies"),
    retrieve=extend_schema(tags=["movies"], summary="Retrieve a movie by ID"),
)
class MovieViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/movies/          → paginated list (cached via Redis, TC.3.2)
    GET /api/movies/<id>/     → detail
    """

    queryset = Movie.objects.filter(is_active=True)
    serializer_class = MovieSerializer
    permission_classes = [AllowAny]

    @method_decorator(cache_page(CACHE_TTL_SECONDS))
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)


# ── Casos 3 & 4: Sessões + Mapa de Assentos ──────────────────────────────────
@extend_schema_view(
    list=extend_schema(tags=["sessions"], summary="List all sessions"),
    retrieve=extend_schema(tags=["sessions"], summary="Retrieve a session by ID"),
    seats=extend_schema(tags=["sessions"], summary="Seat map for a session"),
)
class SessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/sessions/              → paginated list (cached via Redis, TC.3.2)
    GET /api/sessions/<id>/         → detail
    GET /api/sessions/<id>/seats/   → seat map (Caso 4)
    """

    queryset = Session.objects.select_related("movie").all()
    serializer_class = SessionSerializer

    def get_permissions(self):
        if self.action in ["reserve", "checkout"]:
            return [IsAuthenticated()]
        return [AllowAny()]

    @method_decorator(cache_page(CACHE_TTL_SECONDS))
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="seats", url_name="seats")
    def seats(self, request: Request, pk: str | None = None) -> Response:
        """
        Returns the seat map for a specific session.

        Response: list of {id, row, number, status} ordered by (row, number).
        The `status` field will be one of: 'available', 'reserved', 'purchased'.
        'reserved' occurs if the seat is locked in Redis for this session.
        """
        session = self.get_object()
        seats = list(Seat.objects.filter(session=session).order_by("row", "number"))
        seat_ids = [s.id for s in seats]

        # Check Redis for locks
        locked_ids = get_locked_seat_ids(seat_ids)

        # Serialize and override status if locked
        data = []
        for seat in seats:
            serializer = SeatSerializer(seat)
            item = serializer.data
            if seat.id in locked_ids and item["status"] == Seat.Status.AVAILABLE:
                item["status"] = Seat.Status.RESERVED
            data.append(item)

        return Response(data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"seats/(?P<seat_id>\d+)/reserve",
        url_name="reserve-seat",
    )
    def reserve(self, request: Request, pk: str | None = None, seat_id: str | None = None) -> Response:
        """
        Acquire a 10-minute Redis lock on a specific seat.
        POST /api/sessions/<id>/seats/<seat_id>/reserve/
        """
        session = self.get_object()
        try:
            seat = Seat.objects.get(pk=seat_id, session=session)
        except Seat.DoesNotExist:
            return Response({"error": "Seat not found."}, status=status.HTTP_404_NOT_FOUND)

        if seat.status != Seat.Status.AVAILABLE:
            return Response({"error": "Seat is already taken."}, status=status.HTTP_409_CONFLICT)

        if lock_seat(seat.id, request.user.id):
            return Response({"message": "Seat successfully locked for 10 minutes."}, status=status.HTTP_201_CREATED)

        return Response({"error": "Seat is currently being reserved by another user."}, status=status.HTTP_409_CONFLICT)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"seats/(?P<seat_id>\d+)/checkout",
        url_name="checkout-seat",
    )
    def checkout(self, request: Request, pk: str | None = None, seat_id: str | None = None) -> Response:
        """
        Finalize the purchase of a locked seat.
        POST /api/sessions/<id>/seats/<seat_id>/checkout/
        """
        session = self.get_object()
        try:
            seat = Seat.objects.get(pk=seat_id, session=session)
        except Seat.DoesNotExist:
            return Response({"error": "Seat not found."}, status=status.HTTP_404_NOT_FOUND)

        # checkout_seat service handles all checks and the transaction
        try:
            ticket = checkout_seat(seat, request.user)
            serializer = TicketSerializer(ticket)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"error": str(e.detail[0])}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "Database error during checkout."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
