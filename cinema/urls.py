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
