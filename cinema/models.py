from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Movie(models.Model):
    title = models.CharField(_("title"), max_length=255, db_index=True)
    genre = models.CharField(_("genre"), max_length=100, db_index=True)
    duration_minutes = models.PositiveSmallIntegerField(_("duration (min)"))
    release_date = models.DateField(_("release date"), db_index=True)
    synopsis = models.TextField(_("synopsis"), blank=True)
    poster_url = models.URLField(_("poster URL"), blank=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-release_date"]
        verbose_name = _("movie")
        verbose_name_plural = _("movies")

    def __str__(self) -> str:
        return self.title


class Session(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="sessions",
        db_index=True,
    )
    room = models.CharField(_("room"), max_length=50, db_index=True)
    starts_at = models.DateTimeField(_("starts at"), db_index=True)
    ends_at = models.DateTimeField(_("ends at"))
    total_seats = models.PositiveSmallIntegerField(_("total seats"))
    available_seats = models.PositiveSmallIntegerField(_("available seats"))
    price = models.DecimalField(_("price (BRL)"), max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["movie", "starts_at"], name="session_movie_starts_idx"),
        ]
        verbose_name = _("session")
        verbose_name_plural = _("sessions")

    def __str__(self) -> str:
        return f"{self.movie.title} — {self.room} @ {self.starts_at:%Y-%m-%d %H:%M}"


class Seat(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", _("Available")
        RESERVED = "reserved", _("Reserved")
        PURCHASED = "purchased", _("Purchased")

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="seats",
        db_index=True,
    )
    row = models.CharField(_("row"), max_length=5)
    number = models.PositiveSmallIntegerField(_("number"))
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )

    class Meta:
        unique_together = [("session", "row", "number")]
        indexes = [
            models.Index(fields=["session", "status"], name="seat_session_status_idx"),
        ]
        ordering = ["row", "number"]
        verbose_name = _("seat")
        verbose_name_plural = _("seats")

    def __str__(self) -> str:
        return f"{self.row}{self.number} [{self.get_status_display()}]"


class Ticket(models.Model):
    class Status(models.TextChoices):
        LOCKED = "locked", _("Locked")
        PURCHASED = "purchased", _("Purchased")
        EXPIRED = "expired", _("Expired")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
        db_index=True,
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="tickets",
        db_index=True,
    )
    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE,
        related_name="tickets",
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=Status.choices,
        default=Status.LOCKED,
        db_index=True,
    )
    locked_until = models.DateTimeField(_("locked until"), null=True, blank=True)
    purchased_at = models.DateTimeField(_("purchased at"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("session", "seat")]
        indexes = [
            models.Index(fields=["user", "status"], name="ticket_user_status_idx"),
        ]
        ordering = ["-created_at"]
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")

    def __str__(self) -> str:
        return f"Ticket #{self.pk} — {self.user} / {self.seat}"
