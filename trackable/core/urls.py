from django.urls import path
from . import views
from . import setup_views

urlpatterns = [
    path("",             views.landing,     name="landing"),
    path("impressum/",   views.impressum,   name="impressum"),
    path("datenschutz/", views.datenschutz, name="datenschutz"),
    path("setup/",         setup_views.setup_step1, name="setup_step1"),
    path("setup/step2/",   setup_views.setup_step2, name="setup_step2"),
    path("setup/done/",    setup_views.setup_done,  name="setup_done"),
]
