from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat_view, name='chat'),
    path('ask/', views.ask_luna, name='ask_luna'),
]
