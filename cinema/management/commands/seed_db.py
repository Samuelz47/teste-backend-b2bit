from django.core.management.base import BaseCommand
from cinema.models import Movie, Session, Seat
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = "Seeds the database with initial movies, sessions, and seats for testing."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting database seed...")

        if Movie.objects.filter(title="O Auto da Compadecida 2").exists():
            self.stdout.write(self.style.WARNING("Database already seeded. Skipping."))
            return

        movie1 = Movie.objects.create(
            title="O Auto da Compadecida 2",
            genre="Comédia",
            duration_minutes=120,
            release_date=timezone.now().date(),
            synopsis="João Grilo e Chicó estão de volta para mais confusões no Sertão.",
            is_active=True
        )

        movie2 = Movie.objects.create(
            title="Duna: Parte 2",
            genre="Ficção Científica",
            duration_minutes=166,
            release_date=timezone.now().date() - timedelta(days=10),
            synopsis="A jornada mítica de Paul Atreides...",
            is_active=True
        )

        session1 = Session.objects.create(
            movie=movie1,
            room="Sala VIP",
            starts_at=timezone.now() + timedelta(days=1, hours=19),
            ends_at=timezone.now() + timedelta(days=1, hours=21),
            total_seats=20,
            available_seats=20,
            price=35.00
        )

        # Create 2 rows of 10 seats
        for row in ["A", "B"]:
            for i in range(1, 11):
                Seat.objects.create(session=session1, row=row, number=i)
        
        session2 = Session.objects.create(
            movie=movie2,
            room="Sala IMAX",
            starts_at=timezone.now() + timedelta(days=2, hours=20),
            ends_at=timezone.now() + timedelta(days=2, hours=23),
            total_seats=50,
            available_seats=50,
            price=45.00
        )

        for row in ["A", "B", "C", "D", "E"]:
            for i in range(1, 11):
                Seat.objects.create(session=session2, row=row, number=i)

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with 2 movies, 2 sessions, and 70 seats!"))
