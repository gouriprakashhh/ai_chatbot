# dashboard/urls.py - COMPLETE URL CONFIGURATION

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # ============================================
    # ONBOARDING ROUTES
    # ============================================
  path('onboarding/', views.onboarding, name='onboarding'),
    path('onboarding/save/', views.save_onboarding_data, name='save_onboarding_direct'),
    path('onboarding/skip/', views.skip_onboarding_question, name='skip_question_direct'),
    
    # ============================================
    # MAIN DASHBOARD
    # ============================================
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # ============================================
    # PROFILE MANAGEMENT
    # ============================================
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('get-user-data/', views.get_user_data, name='get_user_data'),
    path('update-profile/', views.update_profile, name='update_profile'),
    
    # ============================================
    # MAIN FEATURES
    # ============================================
    path('cycle-tracker/', views.cycle_tracker, name='cycle_tracker'),
    path('symptoms/', views.symptoms, name='symptoms'),
    path('nutrition/', views.nutrition, name='nutrition'),
    path('wellness/', views.wellness, name='wellness'),
    path('exercise/', views.exercise, name='exercise'),
    
    # ============================================
    # COMMUNITY & RESOURCES
    # ============================================
    path('community/', views.community, name='community'),
    path('resources/', views.resources, name='resources'),
    path('resources/articles/', views.resources, name='resources_articles'),  # Alias
    
    # ============================================
    # SETTINGS & SUPPORT
    # ============================================
    path('settings/', views.user_settings, name='settings'),
    path('help/', views.help_support, name='help_support'),
    
    # ============================================
    # API ENDPOINTS - CYCLE TRACKER
    # ============================================
    path('api/update-period-date/', views.update_period_date, name='update_period_date'),
    path('api/update-cycle-length/', views.update_cycle_length, name='update_cycle_length'),
    path('api/cycle-predictions/', views.get_cycle_predictions, name='cycle_predictions'),
    
    # ============================================
    # API ENDPOINTS - SYMPTOMS TRACKER
    # ============================================
    path('api/log-symptom/', views.log_symptom, name='log_symptom'),
    path('api/symptom-history/', views.get_symptom_history, name='symptom_history'),
    
    # ============================================
    # QUICK ACTIONS (Aliases for convenience)
    # ============================================
    path('symptoms/log/', views.symptoms, name='log_symptoms'),
    path('meals/plan/', views.nutrition, name='meal_planning'),

     # NUTRITION ROUTES - NEW
    path('nutrition/', views.nutrition, name='nutrition'),
    path('nutrition/generate-meal/', views.generate_meal_plan, name='generate_meal'),
    path('nutrition/save-meal/', views.save_meal_plan, name='save_meal'),
    path('nutrition/get-tip/', views.get_nutrition_tip, name='get_nutrition_tip'),
    path('nutrition/log-water/', views.log_water_intake, name='log_water'),
    path('nutrition/meal-history/', views.get_meal_history, name='meal_history'),
    
]