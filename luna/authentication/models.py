from django.db import models
from django.utils import timezone
import uuid
import bcrypt

class UserAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255, blank=True, null=True)  # optional for Google
    is_verified = models.BooleanField(default=False)
    auth_provider = models.CharField(
        max_length=20,
        choices=[("email", "Email/Password"), ("google", "Google")],
        default="email"
    )
    created_at = models.DateTimeField(default=timezone.now)

    def set_password(self, raw_password):
        self.password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, raw_password):
        if not self.password:
            return False
        try:
            return bcrypt.checkpw(raw_password.encode(), self.password.encode())
        except ValueError:
            return False

    def __str__(self):
        return self.username



class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.email} - {self.otp}"


class SessionStore(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, null=True, blank=True)
    is_guest = models.BooleanField(default=True)
    data = models.JSONField(default=dict)  # save important details here
    created_at = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Session {self.session_id}"
