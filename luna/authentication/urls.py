from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home_view, name='home'),
    path('home-auth/', views.home_view_test, name='home_auth'),  # Authenticated home
    path('articles/',views.articles,name="articles"),
    path('info/',views.info,name="info"),

    # Auth
    path('signup/', views.signup_view, name='signup'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),

    # Google Login
    path('google-login/', views.google_login_view, name='google_login'),
    path('google-login/callback/', views.google_login_callback_view, name='google_login_callback'),

    # Google Signup
    path('google-signup/', views.google_signup_view, name='google_signup'),
    path('google-signup/callback/', views.google_signup_callback_view, name='google_signup_callback'),
]
