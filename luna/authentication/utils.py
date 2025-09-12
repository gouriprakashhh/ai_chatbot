import random
from django.core.mail import send_mail
from .models import EmailOTP

def generate_otp(email):
    otp = str(random.randint(100000, 999999))
    EmailOTP.objects.create(email=email, otp=otp)
    return otp

def send_otp_email(email, otp):
    send_mail(
        "Your Verification OTP",
        f"Your OTP is {otp}",
        "noreply@yourapp.com",
        [email],
        fail_silently=False,
    )
