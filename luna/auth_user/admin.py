from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PCOSUserData, SymptomLog, MealPlan, CommunityPost, 
    CommunityComment, ExercisePlan, WellnessGoal, 
    Resource, Notification, UserPreferences
)


@admin.register(PCOSUserData)
class PCOSUserDataAdmin(admin.ModelAdmin):
    list_display = ['user', 'pcos_status', 'cycle_day_display', 'activity_score_display', 'updated_at']
    list_filter = ['pcos_status', 'stress_level', 'completed_at']
    search_fields = ['user__username', 'user__email', 'primary_concerns']
    readonly_fields = ['completed_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'completed_at', 'updated_at')
        }),
        ('Cycle Information', {
            'fields': ('cycle_length', 'last_period_date')
        }),
        ('PCOS Status', {
            'fields': ('pcos_status', 'diagnosis_length', 'primary_concerns')
        }),
        ('Mental Wellbeing', {
            'fields': ('mood', 'stress_level')
        }),
        ('Lifestyle', {
            'fields': ('diet_description', 'activity_frequency', 'support_needed')
        }),
    )
    
    def cycle_day_display(self, obj):
        return f"Day {obj.get_cycle_day()}"
    cycle_day_display.short_description = "Current Cycle Day"
    
    def activity_score_display(self, obj):
        score = obj.get_activity_score()
        color = 'green' if score >= 4 else 'orange' if score >= 3 else 'red'
        return format_html(
            '<span style="color: {};">{}/5</span>',
            color, score
        )
    activity_score_display.short_description = "Activity Score"


@admin.register(SymptomLog)
class SymptomLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'energy_level', 'mood_score', 'cramps', 'created_at']
    list_filter = ['date', 'acne', 'hair_loss']
    search_fields = ['user__username', 'notes']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'date')
        }),
        ('Physical Symptoms', {
            'fields': ('cramps', 'bloating', 'acne', 'hair_loss')
        }),
        ('Energy & Mood', {
            'fields': ('energy_level', 'mood_score')
        }),
        ('Additional Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'meal_type', 'calories', 'is_pcos_friendly', 'is_favorite']
    list_filter = ['meal_type', 'is_pcos_friendly', 'is_favorite']
    search_fields = ['name', 'user__username', 'ingredients']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'meal_type', 'description')
        }),
        ('Recipe Details', {
            'fields': ('ingredients', 'instructions')
        }),
        ('Nutritional Information', {
            'fields': ('calories', 'protein', 'carbs', 'fats')
        }),
        ('Preferences', {
            'fields': ('is_pcos_friendly', 'is_favorite')
        }),
    )


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'likes_count', 'comments_count', 'is_pinned', 'created_at']
    list_filter = ['category', 'is_pinned', 'is_featured', 'created_at']
    search_fields = ['title', 'content', 'author__username']
    readonly_fields = ['likes_count', 'comments_count', 'views_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Post Information', {
            'fields': ('author', 'title', 'content', 'category')
        }),
        ('Engagement', {
            'fields': ('likes_count', 'comments_count', 'views_count')
        }),
        ('Moderation', {
            'fields': ('is_pinned', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['pin_posts', 'unpin_posts', 'feature_posts']
    
    def pin_posts(self, request, queryset):
        queryset.update(is_pinned=True)
    pin_posts.short_description = "Pin selected posts"
    
    def unpin_posts(self, request, queryset):
        queryset.update(is_pinned=False)
    unpin_posts.short_description = "Unpin selected posts"
    
    def feature_posts(self, request, queryset):
        queryset.update(is_featured=True)
    feature_posts.short_description = "Feature selected posts"


@admin.register(CommunityComment)
class CommunityCommentAdmin(admin.ModelAdmin):
    list_display = ['short_content', 'author', 'post_title', 'likes_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'author__username', 'post__title']
    readonly_fields = ['likes_count', 'created_at', 'updated_at']
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = "Content"
    
    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = "Post"


@admin.register(ExercisePlan)
class ExercisePlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'exercise_type', 'duration_minutes', 'difficulty_level', 'is_completed']
    list_filter = ['exercise_type', 'difficulty_level', 'is_completed']
    search_fields = ['name', 'user__username', 'description']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'description', 'exercise_type', 'difficulty_level')
        }),
        ('Exercise Details', {
            'fields': ('duration_minutes', 'instructions', 'benefits')
        }),
        ('Progress Tracking', {
            'fields': ('is_completed', 'completed_date')
        }),
    )


@admin.register(WellnessGoal)
class WellnessGoalAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'goal_type', 'progress_display', 'target_date', 'is_completed']
    list_filter = ['goal_type', 'is_completed', 'created_at']
    search_fields = ['title', 'user__username', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Goal Information', {
            'fields': ('user', 'title', 'description', 'goal_type')
        }),
        ('Target & Progress', {
            'fields': ('target_value', 'current_value', 'progress_percentage')
        }),
        ('Timeline', {
            'fields': ('start_date', 'target_date', 'is_completed', 'completed_date')
        }),
    )
    
    def progress_display(self, obj):
        progress = obj.calculate_progress()
        color = 'green' if progress >= 75 else 'orange' if progress >= 50 else 'red'
        return format_html(
            '<div style="width: 100px; background: #f0f0f0; border-radius: 5px;">'
            '<div style="width: {}%; background: {}; height: 20px; border-radius: 5px; text-align: center; color: white;">'
            '{}%'
            '</div></div>',
            progress, color, progress
        )
    progress_display.short_description = "Progress"


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'resource_type', 'category', 'author', 'views_count', 'is_featured']
    list_filter = ['resource_type', 'category', 'is_featured', 'created_at']
    search_fields = ['title', 'description', 'author']
    readonly_fields = ['views_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Resource Information', {
            'fields': ('title', 'description', 'resource_type', 'category')
        }),
        ('Content', {
            'fields': ('content', 'author', 'source_url')
        }),
        ('Visibility', {
            'fields': ('is_featured', 'views_count')
        }),
    )
    
    actions = ['feature_resources', 'unfeature_resources']
    
    def feature_resources(self, request, queryset):
        queryset.update(is_featured=True)
    feature_resources.short_description = "Feature selected resources"
    
    def unfeature_resources(self, request, queryset):
        queryset.update(is_featured=False)
    unfeature_resources.short_description = "Unfeature selected resources"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username']
    readonly_fields = ['created_at']
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Mark as unread"


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_notifications', 'push_notifications', 'theme', 'profile_visibility']
    list_filter = ['theme', 'profile_visibility', 'email_notifications', 'push_notifications']
    search_fields = ['user__username']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Notification Settings', {
            'fields': ('email_notifications', 'push_notifications', 'cycle_reminders', 'daily_tips')
        }),
        ('Privacy Settings', {
            'fields': ('profile_visibility',)
        }),
        ('Display Settings', {
            'fields': ('theme', 'language')
        }),
        ('Data Settings', {
            'fields': ('data_sharing',)
        }),
    )