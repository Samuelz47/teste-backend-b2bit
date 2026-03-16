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
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Movie, Seat, Session
from .serializers import (
    MovieSerializer,
    SeatSerializer,
    SessionSerializer,
    UserRegistrationSerializer,
)

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
    permission_classes = [AllowAny]

    @method_decorator(cache_page(CACHE_TTL_SECONDS))
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="seats", url_name="seats")
    def seats(self, request: Request, pk: str | None = None) -> Response:
        """
        Returns the seat map for a specific session.

        Response: list of {id, row, number, status} ordered by (row, number).
        The `status` field will be one of: 'available', 'reserved', 'purchased'.
        """
        session = self.get_object()
        seats = Seat.objects.filter(session=session).order_by("row", "number")
        serializer = SeatSerializer(seats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
