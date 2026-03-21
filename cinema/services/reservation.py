from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_redis import get_redis_connection
from rest_framework.exceptions import ValidationError

from cinema.models import Seat, Ticket

logger = logging.getLogger(__name__)


def get_seat_lock_key(seat_id: int) -> str:
    return f"seat_lock:{seat_id}"


def lock_seat(seat_id: int, user_id: int) -> bool:
    con = get_redis_connection("default")
    key = get_seat_lock_key(seat_id)
    timeout = getattr(settings, "SEAT_LOCK_TIMEOUT_SECONDS", 600)
    success = con.set(key, user_id, nx=True, ex=timeout)
    return bool(success)


def is_seat_locked(seat_id: int) -> bool:
    con = get_redis_connection("default")
    key = get_seat_lock_key(seat_id)
    return bool(con.exists(key))


def get_locked_seat_ids(seat_ids: list[int]) -> set[int]:
    if not seat_ids:
        return set()

    con = get_redis_connection("default")
    keys = [get_seat_lock_key(sid) for sid in seat_ids]
    values = con.mget(keys)

    locked_ids = set()
    for sid, val in zip(seat_ids, values):
        if val is not None:
            locked_ids.add(sid)
    return locked_ids


def checkout_seat(seat: Seat, user) -> Ticket:
    seat_id = seat.id
    con = get_redis_connection("default")
    key = get_seat_lock_key(seat_id)

    locked_user_id = con.get(key)
    if locked_user_id is None:
        raise ValidationError("Seat lock has expired or never existed.")

    if int(locked_user_id) != user.id:
        raise ValidationError("This seat is locked by another user.")

    try:
        with transaction.atomic():
            seat = Seat.objects.select_for_update().get(pk=seat_id)

            if seat.status != Seat.Status.AVAILABLE:
                raise ValidationError(f"Seat is already {seat.status}.")

            seat.status = Seat.Status.PURCHASED
            seat.save()

            session = seat.session
            session.available_seats = max(0, session.available_seats - 1)
            session.save()

            ticket = Ticket.objects.create(
                user=user,
                session=seat.session,
                seat=seat,
                status=Ticket.Status.PURCHASED,
                purchased_at=timezone.now(),
            )

            con.delete(key)

            return ticket
    except Exception as e:
        logger.error(f"Checkout failed for seat {seat_id}: {e}")
        raise
