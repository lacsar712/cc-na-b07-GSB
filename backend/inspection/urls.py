from django.urls import path

from inspection import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.list_view, name="list"),
    path("archives/", views.archive_book_view, name="archive_book"),
    path("inspections/new/", views.create_view, name="create"),
    path("inspections/<int:pk>/", views.detail_view, name="detail"),
    path("inspections/<int:pk>/archive/", views.archive_view, name="archive"),
    path("inspections/<int:pk>/correct/", views.correct_view, name="correct"),
]
