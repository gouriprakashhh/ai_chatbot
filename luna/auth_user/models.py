from django.db import models
from authentication.models import UserAccount  # link to your auth app


class PCOSUserInfo(models.Model):
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE)
    cycle_length = models.CharField(max_length=50, blank=True)
    last_period_date = models.DateField(blank=True, null=True)
    pcos_status = models.CharField(max_length=50)
    mood_stress = models.CharField(max_length=50)
    goal = models.CharField(max_length=100)

    def __str__(self):
        return self.user.username

from django.db import models
from authentication.models import UserAccount  # Your custom user model

from django.db import models
from django.utils import timezone
from authentication.models import UserAccount  # Assuming your user model

class PCOSUserData(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, unique=True)  # Each user has only one record
    cycle_length = models.CharField(max_length=50, blank=True, null=True)
    last_period_date = models.DateField(blank=True, null=True)
    pcos_status = models.CharField(max_length=50, blank=True, null=True)
    mood = models.CharField(max_length=50, blank=True, null=True)
    stress_level = models.CharField(max_length=50, blank=True, null=True)
    diagnosis_length = models.CharField(max_length=50, blank=True, null=True)
    primary_concerns = models.TextField(blank=True, null=True)
    diet_description = models.TextField(blank=True, null=True)
    activity_frequency = models.CharField(max_length=50, blank=True, null=True)
    support_needed = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"PCOS Data for {self.user.username}"

    class Meta:
        verbose_name = "PCOS User Data"
        verbose_name_plural = "PCOS User Data"

