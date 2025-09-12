from django.contrib import admin
from .models import EmailOTP, SessionStore, UserAccount
# Register your models here.



admin.site.register(EmailOTP)
admin.site.register(SessionStore)