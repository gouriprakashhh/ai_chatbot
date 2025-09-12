from django.db import models
from authentication.models import UserAccount

class ChatSession(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    conversation = models.JSONField(default=list, blank=True)
    memory = models.TextField(blank=True, null=True)  # 🧠 long-term memory summary
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def add_message(self, role, content):
        conv = self.conversation
        conv.append({"role": role, "content": content})
        self.conversation = conv
        self.save(update_fields=["conversation", "updated_at"])

    def clear_memory(self):
        """Clear both conversation and long-term memory"""
        self.conversation = []
        self.memory = ""
        self.save(update_fields=["conversation", "memory", "updated_at"])

    def __str__(self):
        return f"Chat with {self.user.username} ({self.session_id})"

# Add this to your existing models.py

from django.db import models
from authentication.models import UserAccount

class UserData(models.Model):
    """Store dynamically extracted user data"""
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='user_data')
    key = models.CharField(max_length=255)  # e.g., 'weight', 'age', 'favorite_color', etc.
    value = models.TextField()  # Store as text, can be converted later
    data_type = models.CharField(max_length=50, default='string')  # 'string', 'number', 'date', etc.
    confidence_score = models.FloatField(default=1.0)  # AI confidence in extraction
    source_message = models.TextField(blank=True, null=True)  # Original message that contained this data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'key')  # One value per key per user
        indexes = [
            models.Index(fields=['user', 'key']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.key}: {self.value}"

    def get_typed_value(self):
        """Return value converted to appropriate Python type"""
        if self.data_type == 'number':
            try:
                return float(self.value) if '.' in self.value else int(self.value)
            except ValueError:
                return self.value
        elif self.data_type == 'boolean':
            return self.value.lower() in ['true', 'yes', '1', 'on']
        elif self.data_type == 'list':
            try:
                import json
                return json.loads(self.value)
            except:
                return self.value.split(',')
        return self.value