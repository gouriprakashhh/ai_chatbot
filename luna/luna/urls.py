from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('authentication.urls')),
    path('', include('auth_user.urls')),
    path('', include('chatbot.urls')),  # include our app urls
]
