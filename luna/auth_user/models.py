# dashboard/models.py - COMPLETE MODELS

from django.db import models
from django.utils import timezone
from authentication.models import UserAccount


class PCOSUserData(models.Model):
    """
    Comprehensive PCOS user data model
    Stores all health-related information for personalized insights
    """
    user = models.OneToOneField(
        UserAccount, 
        on_delete=models.CASCADE, 
        related_name='pcos_data',
        help_text="User this PCOS data belongs to"
    )
    
    # Cycle Information
    cycle_length = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Average cycle length in days or description"
    )
    last_period_date = models.DateField(
        blank=True, 
        null=True,
        help_text="First day of last menstrual period"
    )
    
    # PCOS Status & Diagnosis
    pcos_status = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Current PCOS management status"
    )
    diagnosis_length = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="How long user has been diagnosed"
    )
    
    # Mental Health & Wellbeing
    mood = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Current mood state"
    )
    stress_level = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Current stress level"
    )
    
    # Health Concerns
    primary_concerns = models.TextField(
        blank=True, 
        null=True,
        help_text="Main PCOS-related concerns"
    )
    
    # Lifestyle
    diet_description = models.TextField(
        blank=True, 
        null=True,
        help_text="Current diet and eating habits"
    )
    activity_frequency = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Physical activity frequency"
    )
    
    # Support Preferences
    support_needed = models.TextField(
        blank=True, 
        null=True,
        help_text="Type of support user is seeking"
    )
    
    # Metadata
    completed_at = models.DateTimeField(
        default=timezone.now,
        help_text="When onboarding was completed"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time data was updated"
    )

    class Meta:
        verbose_name = "PCOS User Data"
        verbose_name_plural = "PCOS User Data"
        ordering = ['-updated_at']

    def __str__(self):
        return f"PCOS Data for {self.user.username}"
    
    def get_cycle_day(self):
        """Calculate current cycle day"""
        if not self.last_period_date:
            return 1
        
        days_since = (timezone.now().date() - self.last_period_date).days
        
        try:
            cycle_length = int(''.join(filter(str.isdigit, str(self.cycle_length))))
        except (ValueError, AttributeError):
            cycle_length = 28
        
        return (days_since % cycle_length) + 1
    
    def get_activity_score(self):
        """Convert activity frequency to numeric score (1-5)"""
        if not self.activity_frequency:
            return 3
        
        activity_lower = self.activity_frequency.lower()
        
        if any(word in activity_lower for word in ["daily", "every day"]):
            return 5
        elif any(word in activity_lower for word in ["4", "5", "6"]):
            return 4
        elif any(word in activity_lower for word in ["2", "3"]):
            return 3
        elif "once" in activity_lower or "1" in activity_lower:
            return 2
        else:
            return 1
    
    def get_nutrition_score(self):
        """Calculate nutrition score (0-100)"""
        if not self.diet_description:
            return 75
        
        diet_lower = self.diet_description.lower()
        
        positive = ["balanced", "healthy", "nutritious", "whole", "clean"]
        negative = ["processed", "junk", "poor", "unhealthy", "irregular"]
        
        positive_count = sum(1 for word in positive if word in diet_lower)
        negative_count = sum(1 for word in negative if word in diet_lower)
        
        base_score = 75
        score = base_score + (positive_count * 5) - (negative_count * 5)
        
        return max(50, min(95, score))


class SymptomLog(models.Model):
    """
    Daily symptom tracking
    Stores comprehensive symptom data for analysis and export
    """
    user = models.ForeignKey(
        UserAccount, 
        on_delete=models.CASCADE, 
        related_name='symptom_logs'
    )
    date = models.DateField(default=timezone.now)
    
    # Physical Symptoms (0-10 scale)
    cramps = models.IntegerField(
        default=0, 
        help_text="Pain level 0-10"
    )
    bloating = models.IntegerField(
        default=0, 
        help_text="Bloating level 0-10"
    )
    
    # Boolean Symptoms
    acne = models.BooleanField(default=False)
    hair_loss = models.BooleanField(default=False)
    
    # Energy & Mood (0-10 scale)
    energy_level = models.IntegerField(
        default=5, 
        help_text="Energy level 0-10"
    )
    mood_score = models.IntegerField(
        default=5, 
        help_text="Mood score 0-10"
    )
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.date}"
    
    def get_severity_level(self):
        """Calculate overall severity based on symptoms"""
        if self.cramps <= 3:
            return "Mild"
        elif self.cramps <= 6:
            return "Moderate"
        else:
            return "Severe"
    
    def get_symptom_count(self):
        """Count number of active symptoms"""
        count = 0
        if self.acne:
            count += 1
        if self.hair_loss:
            count += 1
        if self.cramps > 0:
            count += 1
        if self.bloating > 0:
            count += 1
        return count


class MealPlan(models.Model):
    """
    Personalized meal plans
    Future feature for nutrition guidance
    """
    user = models.ForeignKey(
        UserAccount, 
        on_delete=models.CASCADE, 
        related_name='meal_plans'
    )
    name = models.CharField(max_length=200)
    description = models.TextField()
    meal_type = models.CharField(
        max_length=20,
        choices=[
            ('breakfast', 'Breakfast'),
            ('lunch', 'Lunch'),
            ('dinner', 'Dinner'),
            ('snack', 'Snack')
        ]
    )
    ingredients = models.TextField(help_text="Comma-separated ingredients")
    instructions = models.TextField()
    
    # Nutritional Information
    calories = models.IntegerField(null=True, blank=True)
    protein = models.FloatField(null=True, blank=True, help_text="Grams")
    carbs = models.FloatField(null=True, blank=True, help_text="Grams")
    fats = models.FloatField(null=True, blank=True, help_text="Grams")
    
    # Flags
    is_pcos_friendly = models.BooleanField(default=True)
    is_favorite = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.meal_type}"


class CommunityPost(models.Model):
    """
    Community forum posts
    For peer support and shared experiences
    """
    author = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(
        max_length=50,
        choices=[
            ('general', 'General Discussion'),
            ('success', 'Success Stories'),
            ('nutrition', 'Nutrition & Diet'),
            ('exercise', 'Exercise & Fitness'),
            ('mental_health', 'Mental Health'),
            ('symptoms', 'Symptoms & Management'),
            ('questions', 'Questions & Advice')
        ],
        default='general'
    )
    
    # Engagement Metrics
    likes_count = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    
    # Flags
    is_pinned = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['category', '-created_at']),
        ]
    
    def __str__(self):
        return self.title


class CommunityComment(models.Model):
    """
    Comments on community posts
    """
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField()
    likes_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"


class ExercisePlan(models.Model):
    """
    Personalized exercise plans
    """
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='exercise_plans'
    )
    name = models.CharField(max_length=200)
    description = models.TextField()
    exercise_type = models.CharField(
        max_length=50,
        choices=[
            ('cardio', 'Cardio'),
            ('strength', 'Strength Training'),
            ('yoga', 'Yoga'),
            ('pilates', 'Pilates'),
            ('hiit', 'HIIT'),
            ('walking', 'Walking'),
            ('swimming', 'Swimming'),
            ('cycling', 'Cycling')
        ]
    )
    duration_minutes = models.IntegerField(help_text="Duration in minutes")
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced')
        ],
        default='beginner'
    )
    
    instructions = models.TextField()
    benefits = models.TextField(help_text="PCOS-specific benefits")
    
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.exercise_type}"


class WellnessGoal(models.Model):
    """
    User-defined wellness goals
    Track progress towards health objectives
    """
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='wellness_goals'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal_type = models.CharField(
        max_length=50,
        choices=[
            ('weight', 'Weight Management'),
            ('exercise', 'Exercise Consistency'),
            ('nutrition', 'Nutrition Improvement'),
            ('sleep', 'Better Sleep'),
            ('stress', 'Stress Reduction'),
            ('cycle', 'Cycle Regularity'),
            ('custom', 'Custom Goal')
        ]
    )
    
    target_value = models.CharField(max_length=100, help_text="Target to achieve")
    current_value = models.CharField(max_length=100, blank=True, null=True)
    
    start_date = models.DateField(default=timezone.now)
    target_date = models.DateField()
    
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    
    progress_percentage = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def calculate_progress(self):
        """Calculate goal progress percentage"""
        if self.is_completed:
            return 100
        
        days_total = (self.target_date - self.start_date).days
        days_passed = (timezone.now().date() - self.start_date).days
        
        if days_total > 0:
            return min(100, int((days_passed / days_total) * 100))
        return 0


class Resource(models.Model):
    """
    Educational resources about PCOS
    Articles, videos, guides, etc.
    """
    title = models.CharField(max_length=200)
    description = models.TextField()
    content = models.TextField()
    
    resource_type = models.CharField(
        max_length=50,
        choices=[
            ('article', 'Article'),
            ('video', 'Video'),
            ('guide', 'Guide'),
            ('infographic', 'Infographic'),
            ('research', 'Research Paper')
        ]
    )
    category = models.CharField(
        max_length=50,
        choices=[
            ('basics', 'PCOS Basics'),
            ('nutrition', 'Nutrition'),
            ('exercise', 'Exercise'),
            ('mental_health', 'Mental Health'),
            ('fertility', 'Fertility'),
            ('treatment', 'Treatment Options'),
            ('lifestyle', 'Lifestyle Management')
        ]
    )
    
    author = models.CharField(max_length=100)
    source_url = models.URLField(blank=True, null=True)
    
    is_featured = models.BooleanField(default=False)
    views_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', '-created_at']
    
    def __str__(self):
        return self.title


class Notification(models.Model):
    """
    User notifications for reminders and updates
    """
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('reminder', 'Reminder'),
            ('achievement', 'Achievement'),
            ('community', 'Community Update'),
            ('health', 'Health Tip'),
            ('cycle', 'Cycle Update'),
            ('general', 'General')
        ],
        default='general'
    )
    
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=200, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class UserPreferences(models.Model):
    """
    User preferences and settings
    """
    user = models.OneToOneField(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='preferences'
    )
    
    # Notification Settings
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    cycle_reminders = models.BooleanField(default=True)
    daily_tips = models.BooleanField(default=True)
    
    # Privacy Settings
    profile_visibility = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('private', 'Private'),
            ('friends', 'Friends Only')
        ],
        default='private'
    )
    
    # Display Settings
    theme = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto')
        ],
        default='light'
    )
    language = models.CharField(max_length=10, default='en')
    
    # Data Settings
    data_sharing = models.BooleanField(
        default=False,
        help_text="Share anonymized data for research"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Preferences"
        verbose_name_plural = "User Preferences"
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    


# ADD THIS MODEL TO dashboard/models.py

class WaterIntakeLog(models.Model):
    """
    Daily water intake tracking
    Stores number of glasses consumed each day
    """
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='water_logs'
    )
    date = models.DateField(default=timezone.now)
    glasses = models.IntegerField(
        default=0,
        help_text="Number of glasses (8oz each) consumed"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']
        indexes = [
            models.Index(fields=['user', '-date']),
        ]
        verbose_name = "Water Intake Log"
        verbose_name_plural = "Water Intake Logs"
    
    def __str__(self):
        return f"{self.user.username} - {self.date}: {self.glasses} glasses"
    
    def get_percentage(self, goal=8):
        """Calculate percentage of daily goal achieved"""
        return min(100, int((self.glasses / goal) * 100))