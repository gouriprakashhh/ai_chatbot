from django.urls import path
from . import views


urlpatterns = [
    path('onboarding/', views.onboarding, name='onboarding'),
    path('onboarding/save/', views.save_onboarding_data, name='save_onboarding_data'),
    path('onboarding/skip/', views.skip_onboarding_question, name='skip_onboarding_question'),
    path('dashboard/', views.dashboard, name='dashboard'),
]
