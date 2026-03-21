"""
Cinema app URL configuration.

Routes:
  POST   /api/register/              → User registration (Caso 1)
  GET    /api/movies/                → List movies (Caso 2)
  GET    /api/movies/<id>/           → Movie detail
  GET    /api/sessions/              → List sessions (Caso 3)
  GET    /api/sessions/<id>/         → Session detail
  GET    /api/sessions/<id>/seats/   → Seat map (Caso 4)
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"movies", views.MovieViewSet, basename="movie")
router.register(r"sessions", views.SessionViewSet, basename="session")
router.register(r"tickets", views.TicketViewSet, basename="ticket")

urlpatterns = [
    path("register/", views.UserRegistrationView.as_view(), name="user-register"),
    path("", include(router.urls)),
]
