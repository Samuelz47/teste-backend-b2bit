from __future__ import annotations

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Movie, Seat, Session, Ticket
from .serializers import (
    MovieSerializer,
    SeatSerializer,
    SessionSerializer,
    TicketSerializer,
    UserRegistrationSerializer,
)
from .services.reservation import checkout_seat, get_locked_seat_ids, lock_seat

CACHE_TTL_SECONDS: int = 60 * 5


@extend_schema(tags=["auth"])
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    list=extend_schema(tags=["movies"], summary="List all active movies"),
    retrieve=extend_schema(tags=["movies"], summary="Retrieve a movie by ID"),
)
class MovieViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Movie.objects.filter(is_active=True)
    serializer_class = MovieSerializer
    permission_classes = [AllowAny]

    @method_decorator(cache_page(CACHE_TTL_SECONDS))
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(tags=["sessions"], summary="List all sessions"),
    retrieve=extend_schema(tags=["sessions"], summary="Retrieve a session by ID"),
    seats=extend_schema(tags=["sessions"], summary="Seat map for a session"),
    reserve=extend_schema(
        tags=["sessions"],
        summary="Reserve a seat",
        responses={201: {"type": "object", "properties": {"message": {"type": "string"}}}, 409: {"type": "object", "properties": {"error": {"type": "string"}}}},
    ),
    checkout=extend_schema(
        tags=["sessions"],
        summary="Checkout a reserved seat",
        responses={201: TicketSerializer, 400: {"type": "object", "properties": {"error": {"type": "string"}}}},
    ),
)
class SessionViewSet(viewsets.ReadOnlyModelViewSet):
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
        session = self.get_object()
        seats = list(Seat.objects.filter(session=session).order_by("row", "number"))
        seat_ids = [s.id for s in seats]
        locked_ids = get_locked_seat_ids(seat_ids)
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
        session = self.get_object()
        try:
            seat = Seat.objects.get(pk=seat_id, session=session)
        except Seat.DoesNotExist:
            return Response({"error": "Seat not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ticket = checkout_seat(seat, request.user)
            serializer = TicketSerializer(ticket)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except serializers.ValidationError as e:
            return Response({"error": str(e.detail[0])}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "Database error during checkout."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema_view(
    list=extend_schema(tags=["tickets"], summary="List authenticated user's tickets"),
    retrieve=extend_schema(tags=["tickets"], summary="Retrieve a ticket by ID"),
)
class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Ticket.objects.filter(user=self.request.user).select_related(
            "session", "session__movie", "seat"
        )
