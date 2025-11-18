# dashboard/views.py - COMPLETE UPDATED VERSION

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from datetime import datetime, timedelta
import json
import logging
import calendar
from authentication.models import SessionStore, UserAccount
from .models import PCOSUserData, SymptomLog


logger = logging.getLogger(__name__)


# ============================================
# AUTHENTICATION HELPER
# ============================================
def get_authenticated_user(request):
    """Helper function to get authenticated user from session"""
    session_id = request.session.get("session_id")
    
    if not session_id:
        return None, "login"
    
    try:
        session = SessionStore.objects.get(session_id=session_id)
        user = session.user
        if not user:
            return None, "login"
        return user, None
    except SessionStore.DoesNotExist:
        return None, "login"


# ============================================
# CYCLE CALCULATION HELPERS
# ============================================
def get_cycle_length_number(cycle_length_str):
    """Extract numeric cycle length from string"""
    if not cycle_length_str:
        return 28
    try:
        return int(''.join(filter(str.isdigit, str(cycle_length_str))))
    except (ValueError, AttributeError):
        return 28


def calculate_cycle_info(last_period_date, cycle_length):
    """Calculate comprehensive cycle information"""
    if not last_period_date:
        return {
            'cycle_day': 1,
            'days_until_period': None,
            'days_until_ovulation': None,
            'cycle_progress': 0,
            'current_phase': 'Unknown',
            'phase_description': 'Add your last period date to track your cycle',
            'is_fertile': False,
            'is_period': False,
            'is_ovulation': False
        }
    
    cycle_length_num = get_cycle_length_number(cycle_length)
    days_since_period = (datetime.now().date() - last_period_date).days
    
    if days_since_period < 0:
        days_since_period = 0
    
    cycle_day = (days_since_period % cycle_length_num) + 1
    cycle_progress = (cycle_day / cycle_length_num) * 100
    
    ovulation_day = max(12, min(16, cycle_length_num // 2))
    fertile_start = ovulation_day - 5
    fertile_end = ovulation_day
    
    is_period = cycle_day <= 5
    is_fertile = fertile_start <= cycle_day <= fertile_end
    is_ovulation = abs(cycle_day - ovulation_day) <= 1
    
    if cycle_day <= 5:
        current_phase = 'Menstrual'
        phase_description = 'Rest and self-care time'
        phase_icon = 'fa-tint'
    elif cycle_day <= ovulation_day - 2:
        current_phase = 'Follicular'
        phase_description = 'Energy is rising, great time for activity'
        phase_icon = 'fa-seedling'
    elif abs(cycle_day - ovulation_day) <= 1:
        current_phase = 'Ovulation'
        phase_description = 'Peak fertility window'
        phase_icon = 'fa-star'
    else:
        current_phase = 'Luteal'
        phase_description = 'Prepare for next cycle'
        phase_icon = 'fa-moon'
    
    if cycle_day < ovulation_day:
        days_until_ovulation = ovulation_day - cycle_day
    else:
        days_until_ovulation = (cycle_length_num - cycle_day) + ovulation_day
    
    days_until_period = cycle_length_num - cycle_day
    if days_until_period < 0:
        days_until_period = 0
    
    return {
        'cycle_day': cycle_day,
        'cycle_length': cycle_length_num,
        'days_until_period': days_until_period,
        'days_until_ovulation': days_until_ovulation,
        'cycle_progress': round(cycle_progress, 1),
        'current_phase': current_phase,
        'phase_description': phase_description,
        'phase_icon': phase_icon,
        'is_fertile': is_fertile,
        'is_period': is_period,
        'is_ovulation': is_ovulation,
        'ovulation_day': ovulation_day,
        'fertile_start': fertile_start,
        'fertile_end': fertile_end
    }

def generate_calendar_month(year, month, cycle_info, last_period_date):
    """Generate calendar data for a specific month"""
    cal = calendar.monthcalendar(year, month)
    calendar_days = []
    
    cycle_length = cycle_info['cycle_length']
    
    for week in cal:
        for day in week:
            if day == 0:
                calendar_days.append({
                    'number': '',
                    'class': 'empty',
                    'is_today': False
                })
            else:
                date = datetime(year, month, day).date()
                classes = []
                
                # Check if today
                is_today = date == timezone.now().date()
                if is_today:
                    classes.append('today')
                
                # Calculate cycle day for this date
                if last_period_date:
                    days_since = (date - last_period_date).days
                    if days_since >= 0:
                        date_cycle_day = (days_since % cycle_length) + 1
                        
                        # Determine phase
                        if date_cycle_day <= 5:
                            classes.append('period')
                        elif cycle_info['fertile_start'] <= date_cycle_day <= cycle_info['fertile_end']:
                            if abs(date_cycle_day - cycle_info['ovulation_day']) <= 1:
                                classes.append('ovulation')
                            else:
                                classes.append('fertile')
                
                calendar_days.append({
                    'number': day,
                    'class': ' '.join(classes) if classes else '',
                    'is_today': is_today
                })
    
    return calendar_days


# ============================================
# CYCLE TRACKER VIEW
# ============================================
def cycle_tracker(request):
    """Dynamic cycle tracker with real user data"""
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    
    # Get user's PCOS data
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
    except PCOSUserData.DoesNotExist:
        return redirect("/onboarding/")
    
    # Calculate cycle information
    cycle_info = calculate_cycle_info(
        pcos_data.last_period_date,
        pcos_data.cycle_length
    )
    
    # Get month and year from query params or use current
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')
    
    if month_param and year_param:
        try:
            current_month = int(month_param)
            current_year = int(year_param)
        except ValueError:
            now = timezone.now()
            current_month = now.month
            current_year = now.year
    else:
        now = timezone.now()
        current_month = now.month
        current_year = now.year
    
    # Create date object for the selected month
    month_date = datetime(current_year, current_month, 1)
    month_name = month_date.strftime("%B %Y")
    
    # Calculate previous and next month
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
    
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year
    
    calendar_days = generate_calendar_month(
        current_year,
        current_month,
        cycle_info,
        pcos_data.last_period_date
    )
    
    # Generate phase-specific tips
    phase_tips = {
        'Menstrual': 'Stay hydrated and rest. Iron-rich foods can help replenish what\'s lost during your period.',
        'Follicular': 'Great time for challenging workouts! Your energy is naturally higher during this phase.',
        'Ovulation': 'Peak fertility time. Consider tracking basal temperature if planning pregnancy.',
        'Luteal': 'Focus on stress management. PMS symptoms may appear - be gentle with yourself.'
    }
    
    context = {
        'user_name': user.username,
        'cycle_day': cycle_info['cycle_day'],
        'cycle_length': cycle_info['cycle_length'],
        'days_until_period': cycle_info['days_until_period'],
        'days_until_ovulation': cycle_info['days_until_ovulation'],
        'cycle_progress': cycle_info['cycle_progress'],
        'current_phase': cycle_info['current_phase'],
        'phase_description': cycle_info['phase_description'],
        'phase_icon': cycle_info['phase_icon'],
        'phase_tip': phase_tips.get(cycle_info['current_phase'], 'Track your cycle daily for better insights.'),
        'is_fertile': cycle_info['is_fertile'],
        'is_period': cycle_info['is_period'],
        'is_ovulation': cycle_info['is_ovulation'],
        'month_name': month_name,
        'current_month': current_month,
        'current_year': current_year,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'calendar_days': calendar_days,
        'has_period_data': pcos_data.last_period_date is not None,
        'last_period_date': pcos_data.last_period_date.isoformat() if pcos_data.last_period_date else '',
        'today': datetime.now().date().isoformat()
    }
    
    return render(request, "cycle_tracker.html", context)


# ============================================
# CYCLE TRACKER API ENDPOINTS
# ============================================
@require_POST
@csrf_exempt
def update_period_date(request):
    """Update last period date"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        new_date_str = data.get('last_period_date')
        
        if not new_date_str:
            return JsonResponse({
                "status": "error",
                "message": "Date is required"
            }, status=400)
        
        try:
            new_date = datetime.fromisoformat(new_date_str).date()
        except ValueError:
            return JsonResponse({
                "status": "error",
                "message": "Invalid date format"
            }, status=400)
        
        # Update PCOS data
        pcos_data = PCOSUserData.objects.get(user=user)
        pcos_data.last_period_date = new_date
        pcos_data.save()
        
        logger.info(f"Period date updated for user: {user.username}")
        
        return JsonResponse({
            "status": "success",
            "message": "Period date updated successfully"
        })
        
    except PCOSUserData.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "User data not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating period date: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Internal server error"
        }, status=500)


@require_POST
@csrf_exempt
def update_cycle_length(request):
    """Update cycle length"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        cycle_length = data.get('cycle_length')
        
        if not cycle_length:
            return JsonResponse({
                "status": "error",
                "message": "Cycle length is required"
            }, status=400)
        
        # Update PCOS data
        pcos_data = PCOSUserData.objects.get(user=user)
        pcos_data.cycle_length = cycle_length
        pcos_data.save()
        
        logger.info(f"Cycle length updated for user: {user.username}")
        
        return JsonResponse({
            "status": "success",
            "message": "Cycle length updated successfully"
        })
        
    except PCOSUserData.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "User data not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating cycle length: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Internal server error"
        }, status=500)


# ============================================
# EXISTING VIEWS (keeping all original functionality)
# ============================================

def onboarding(request):
    """Render onboarding page for new users"""
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)

    if PCOSUserData.objects.filter(user=user).exists():
        return redirect("/dashboard/")

    return render(request, "onboard.html", {"user_name": user.username})


@require_POST
@csrf_exempt
def save_onboarding_data(request):
    """Save initial onboarding data"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)

        if PCOSUserData.objects.filter(user=user).exists():
            return JsonResponse({"status": "error", "message": "Onboarding already completed"}, status=400)

        PCOSUserData.objects.create(
            user=user,
            cycle_length=data.get("cycle_length"),
            last_period_date=data.get("last_period_date") or None,
            pcos_status=data.get("pcos_status"),
            mood=data.get("mood"),
            stress_level=data.get("stress_level"),
            diagnosis_length=data.get("diagnosis_length"),
            primary_concerns=data.get("primary_concerns"),
            diet_description=data.get("diet_description"),
            activity_frequency=data.get("activity_frequency"),
            support_needed=data.get("support_needed"),
            completed_at=timezone.now()
        )

        logger.info(f"Onboarding completed for user: {user.username}")

        return JsonResponse({
            "status": "success",
            "message": "Onboarding data saved successfully",
            "redirect_url": "/dashboard/"
        })

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Error saving onboarding data: {str(e)}")
        return JsonResponse({"status": "error", "message": f"Internal server error: {str(e)}"}, status=500)


@require_POST
@csrf_exempt
def skip_onboarding_question(request):
    """Track skipped questions during onboarding"""
    try:
        data = json.loads(request.body)
        question_key = data.get("question_key")
        
        if not request.session.session_key:
            request.session.create()
        
        if 'skipped_questions' not in request.session:
            request.session['skipped_questions'] = []
        
        if question_key and question_key not in request.session['skipped_questions']:
            request.session['skipped_questions'].append(question_key)
            request.session.modified = True
        
        logger.info(f"Question {question_key} skipped for session {request.session.session_key}")
        
        return JsonResponse({"status": "success", "message": "Question skipped"})
        
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Error skipping question: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal server error"}, status=500)


def dashboard(request):
    """Render main dashboard with comprehensive PCOS data"""
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
    except PCOSUserData.DoesNotExist:
        return redirect("/onboarding/")
    
    cycle_info = calculate_cycle_info(pcos_data.last_period_date, pcos_data.cycle_length)
    
    symptom_level = "Mild"
    if pcos_data.stress_level:
        stress_lower = pcos_data.stress_level.lower()
        if any(word in stress_lower for word in ["overwhelming", "severe", "very high"]):
            symptom_level = "Severe"
        elif any(word in stress_lower for word in ["high", "significant"]):
            symptom_level = "Moderate"
    
    nutrition_score = 75
    if pcos_data.diet_description:
        diet_lower = pcos_data.diet_description.lower()
        positive_keywords = ["balanced", "healthy", "nutritious", "whole foods", "clean", "organic", "vegetables"]
        positive_count = sum(1 for keyword in positive_keywords if keyword in diet_lower)
        negative_keywords = ["processed", "junk", "irregular", "poor", "unhealthy", "fast food"]
        negative_count = sum(1 for keyword in negative_keywords if keyword in diet_lower)
        
        if positive_count > negative_count:
            nutrition_score = min(90, 75 + (positive_count * 5))
        elif negative_count > positive_count:
            nutrition_score = max(50, 75 - (negative_count * 5))
    
    activity_mapping = {
        "daily": 5, "almost daily": 5, "4-6 times": 4, "3-4 times": 4,
        "2-3 times": 3, "once": 2, "1-2 times": 2, "rarely": 1, "never": 1,
    }
    
    activity_score = 3
    if pcos_data.activity_frequency:
        activity_lower = pcos_data.activity_frequency.lower()
        for key, value in activity_mapping.items():
            if key in activity_lower:
                activity_score = value
                break
    
    context = {
        'user_name': user.username,
        'cycle_day': cycle_info['cycle_day'],
        'days_until_ovulation': cycle_info['days_until_ovulation'],
        'days_until_period': cycle_info['days_until_period'],
        'cycle_progress': cycle_info['cycle_progress'],
        'symptom_level': symptom_level,
        'nutrition_score': nutrition_score,
        'pcos_status': pcos_data.pcos_status or "Unknown",
        'mood': pcos_data.mood or "Not specified",
        'stress_level': pcos_data.stress_level or "Not specified",
        'primary_concerns': pcos_data.primary_concerns or "None specified",
        'diet_description': pcos_data.diet_description or "Not specified",
        'activity_frequency': pcos_data.activity_frequency or "Not specified",
        'activity_score': activity_score,
        'current_date': timezone.now().strftime("%B %d, %Y"),
    }
    
    return render(request, "dashboard.html", context)


def edit_profile(request):
    """Render the edit profile page with all user data"""
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
    except PCOSUserData.DoesNotExist:
        return redirect("/onboarding/")
    
    context = {
        'user_name': user.username,
        'user_email': user.email if hasattr(user, 'email') else '',
        'today': timezone.now().date().isoformat(),
        'cycle_length': pcos_data.cycle_length or '',
        'last_period_date': pcos_data.last_period_date.isoformat() if pcos_data.last_period_date else '',
        'pcos_status': pcos_data.pcos_status or '',
        'mood': pcos_data.mood or '',
        'stress_level': pcos_data.stress_level or '',
        'diagnosis_length': pcos_data.diagnosis_length or '',
        'primary_concerns': pcos_data.primary_concerns or '',
        'diet_description': pcos_data.diet_description or '',
        'activity_frequency': pcos_data.activity_frequency or '',
        'support_needed': pcos_data.support_needed or '',
    }
    
    return render(request, "edit_profile.html", context)


@require_GET
def get_user_data(request):
    """API endpoint to fetch user's PCOS data"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
        
        data = {
            'cycle_length': pcos_data.cycle_length,
            'last_period_date': pcos_data.last_period_date.isoformat() if pcos_data.last_period_date else None,
            'pcos_status': pcos_data.pcos_status,
            'mood': pcos_data.mood,
            'stress_level': pcos_data.stress_level,
            'diagnosis_length': pcos_data.diagnosis_length,
            'primary_concerns': pcos_data.primary_concerns,
            'diet_description': pcos_data.diet_description,
            'activity_frequency': pcos_data.activity_frequency,
            'support_needed': pcos_data.support_needed,
        }
        
        return JsonResponse({"status": "success", "data": data})
        
    except PCOSUserData.DoesNotExist:
        return JsonResponse({"status": "error", "message": "No PCOS data found"}, status=404)
    except Exception as e:
        logger.error(f"Error fetching user data: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal server error"}, status=500)


@require_POST
@csrf_exempt
def update_profile(request):
    """API endpoint to update user's PCOS data"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        
        try:
            pcos_data = PCOSUserData.objects.get(user=user)
        except PCOSUserData.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "No PCOS data found. Please complete onboarding first."
            }, status=404)
        
        updated_fields = []
        
        if 'cycle_length' in data and data['cycle_length']:
            if pcos_data.cycle_length != data['cycle_length']:
                pcos_data.cycle_length = data['cycle_length']
                updated_fields.append('cycle_length')
        
        if 'last_period_date' in data and data['last_period_date']:
            try:
                new_date = datetime.fromisoformat(data['last_period_date']).date()
                if pcos_data.last_period_date != new_date:
                    pcos_data.last_period_date = new_date
                    updated_fields.append('last_period_date')
            except ValueError:
                logger.warning(f"Invalid date format: {data['last_period_date']}")
        
        field_mapping = {
            'diagnosis_length': 'diagnosis_length',
            'pcos_status': 'pcos_status',
            'mood': 'mood',
            'stress_level': 'stress_level',
            'primary_concerns': 'primary_concerns',
            'diet_description': 'diet_description',
            'activity_frequency': 'activity_frequency',
            'support_needed': 'support_needed'
        }
        
        for request_field, model_field in field_mapping.items():
            if request_field in data and data[request_field]:
                current_value = getattr(pcos_data, model_field)
                new_value = data[request_field]
                if current_value != new_value:
                    setattr(pcos_data, model_field, new_value)
                    updated_fields.append(model_field)
        
        if updated_fields:
            pcos_data.save()
            logger.info(f"Profile updated for user: {user.username}. Updated fields: {', '.join(updated_fields)}")
            
            return JsonResponse({
                "status": "success",
                "message": f"Profile updated successfully! ({len(updated_fields)} field(s) changed)",
                "updated_fields": updated_fields
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": "No changes detected. Please update at least one field."
            }, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return JsonResponse({"status": "error", "message": f"Internal server error: {str(e)}"}, status=500)


# ============================================
# SYMPTOMS TRACKER VIEW
# ============================================
def symptoms(request):
    """Dynamic symptoms tracker with real user data"""
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
    except PCOSUserData.DoesNotExist:
        return redirect("/onboarding/")
    
    # Get cycle info for context
    cycle_info = calculate_cycle_info(pcos_data.last_period_date, pcos_data.cycle_length)
    
    # Get today's date
    today = datetime.now().date()
    
    # Check if user has logged today
    try:
        today_log = SymptomLog.objects.get(user=user, date=today)
        has_logged_today = True
    except SymptomLog.DoesNotExist:
        today_log = None
        has_logged_today = False
    
    # Get recent logs (last 7 days)
    recent_logs = SymptomLog.objects.filter(user=user).order_by('-date')[:7]
    
    # Calculate statistics from last 30 days
    thirty_days_ago = today - timedelta(days=30)
    last_month_logs = SymptomLog.objects.filter(
        user=user,
        date__gte=thirty_days_ago
    ).order_by('date')
    
    # Generate chart data for last 14 days
    chart_dates = []
    pain_data = []
    energy_data = []
    bloating_data = []
    
    for i in range(13, -1, -1):
        date = today - timedelta(days=i)
        chart_dates.append(date.strftime('%b %d'))
        
        log = last_month_logs.filter(date=date).first()
        if log:
            pain_data.append(log.cramps)
            energy_data.append(log.energy_level)
            bloating_data.append(log.bloating)
        else:
            pain_data.append(0)
            energy_data.append(5)
            bloating_data.append(0)
    
    # Calculate insights
    total_logs = last_month_logs.count()
    avg_pain = sum([log.cramps for log in last_month_logs]) / total_logs if total_logs > 0 else 0
    avg_energy = sum([log.energy_level for log in last_month_logs]) / total_logs if total_logs > 0 else 5
    
    # Determine overall feeling
    if avg_pain < 3 and avg_energy > 7:
        overall_feeling = "great"
    elif avg_pain < 5 and avg_energy > 5:
        overall_feeling = "good"
    elif avg_pain < 7:
        overall_feeling = "moderate"
    else:
        overall_feeling = "challenging"
    
    context = {
        'user_name': user.username,
        'cycle_day': cycle_info['cycle_day'],
        'current_phase': cycle_info['current_phase'],
        'today': today.strftime('%B %d, %Y'),
        'today_iso': today.isoformat(),
        'has_logged_today': has_logged_today,
        'today_log': today_log,
        'recent_logs': recent_logs,
        'chart_dates': json.dumps(chart_dates),
        'pain_data': json.dumps(pain_data),
        'energy_data': json.dumps(energy_data),
        'bloating_data': json.dumps(bloating_data),
        'avg_pain': round(avg_pain, 1),
        'avg_energy': round(avg_energy, 1),
        'overall_feeling': overall_feeling,
        'total_logs': total_logs,
    }
    
    return render(request, "symptoms.html", context)


# ============================================
# SYMPTOM LOG API ENDPOINTS - UPDATED
# ============================================
@require_POST
@csrf_exempt
@require_POST
@csrf_exempt
def log_symptom(request):
    """API endpoint to log daily symptoms - creates multiple logs per day"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        
        # Use current date and time for the log
        log_date = data.get('date')
        if log_date:
            try:
                log_date = datetime.fromisoformat(log_date).date()
            except ValueError:
                log_date = datetime.now().date()
        else:
            log_date = datetime.now().date()
        
        # Get symptoms list
        symptoms = data.get('symptoms', [])
        
        # Prepare notes - combine selected symptoms with additional notes
        symptom_notes = []
        if symptoms and len(symptoms) > 0:
            symptom_notes.append("Symptoms: " + ", ".join([s.replace('-', ' ').title() for s in symptoms]))
        
        additional_notes = data.get('notes', '').strip()
        if additional_notes:
            symptom_notes.append(additional_notes)
        
        combined_notes = ". ".join(symptom_notes) if symptom_notes else ""
        
        # Always create a new log entry
        log = SymptomLog.objects.create(
            user=user,
            date=log_date,
            cramps=data.get('cramps', 0),
            bloating=data.get('bloating', 0),
            energy_level=data.get('energy_level', 5),
            mood_score=data.get('mood_score', 5),
            acne='acne' in symptoms,
            hair_loss='hair-loss' in symptoms,
            notes=combined_notes
        )
        
        logger.info(f"New symptom log created for user: {user.username}, date: {log_date}, ID: {log.id}, symptoms: {symptoms}")
        
        return JsonResponse({
            "status": "success",
            "message": "Symptoms logged successfully!",
            "log_id": log.id,
            "date": log.date.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"Error logging symptom: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }, status=500)


@require_GET
def get_symptom_history(request):
    """Get symptom history for charts and export"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        days = int(request.GET.get('days', 30))
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        logs = SymptomLog.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('-date')
        
        data = []
        for log in logs:
            # Collect symptoms that are marked True
            symptoms = []
            if log.acne:
                symptoms.append('acne')
            if log.hair_loss:
                symptoms.append('hair-loss')
            
            # Parse notes for additional symptoms if present
            if log.notes:
                note_lower = log.notes.lower()
                symptom_keywords = {
                    'weight': 'weight-gain',
                    'mood swing': 'mood-swings',
                    'fatigue': 'fatigue',
                    'tired': 'fatigue',
                    'anxiety': 'anxiety',
                    'anxious': 'anxiety',
                    'sleep': 'insomnia',
                    'insomnia': 'insomnia',
                    'nausea': 'nausea',
                    'breast': 'breast-tenderness',
                    'craving': 'cravings',
                    'hungry': 'cravings'
                }
                
                for keyword, symptom in symptom_keywords.items():
                    if keyword in note_lower and symptom not in symptoms:
                        symptoms.append(symptom)
            
            data.append({
                'date': log.date.isoformat(),
                'cramps': log.cramps,
                'bloating': log.bloating,
                'energy_level': log.energy_level,
                'mood_score': log.mood_score,
                'symptoms': symptoms,
                'mood': 'calm',  # Default mood, can be enhanced later
                'acne': log.acne,
                'hair_loss': log.hair_loss,
                'notes': log.notes or ''
            })
        
        return JsonResponse({"status": "success", "data": data})
        
    except Exception as e:
        logger.error(f"Error fetching symptom history: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal server error"}, status=500)


# ============================================
# PLACEHOLDER VIEWS FOR NEW FEATURES
# ============================================



def wellness(request):
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    return render(request, "wellness.html", {"user_name": user.username})

def exercise(request):
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    return render(request, "exercise.html", {"user_name": user.username})

def community(request):
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    return render(request, "community.html", {"user_name": user.username})

def resources(request):
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    return render(request, "resources.html", {"user_name": user.username})

def user_settings(request):
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    return render(request, "settings.html", {"user_name": user.username})

def help_support(request):
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    return render(request, "help.html", {"user_name": user.username})


@require_GET
def get_cycle_predictions(request):
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
        return JsonResponse({
            "status": "success",
            "predictions": {
                "next_period": "2024-01-15",
                "ovulation": "2024-01-05",
                "fertile_window": ["2024-01-03", "2024-01-07"]
            }
        })
    except Exception as e:
        logger.error(f"Error getting predictions: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal server error"}, status=500)
    





# dashboard/nutrition_views.py - COMPLETE NUTRITION BACKEND WITH GEMMA API

from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
import json
import logging
import requests
from authentication.models import SessionStore, UserAccount
from .models import PCOSUserData, MealPlan, WaterIntakeLog

logger = logging.getLogger(__name__)

# Ollama/Gemma API endpoint
GEMMA_API = getattr(settings, "GEMMA_API", "http://localhost:11434/api/generate")

# Predefined recipe database
RECIPE_DATABASE = {
    'quinoa-buddha-bowl': {
        'name': 'Quinoa Buddha Bowl',
        'emoji': '🥗',
        'description': 'Nutrient-dense bowl with quinoa, roasted vegetables, and tahini dressing',
        'prep_time': '25 mins',
        'cook_time': '15 mins',
        'servings': 2,
        'calories': 420,
        'protein': 18,
        'carbs': 52,
        'fats': 16,
        'fiber': 12,
        'benefits': 'High in plant-based protein and fiber, helps stabilize blood sugar levels and reduce inflammation.',
        'ingredients': [
            '1 cup quinoa, rinsed',
            '2 cups water or vegetable broth',
            '1 sweet potato, cubed',
            '1 cup chickpeas, drained',
            '2 cups kale or spinach',
            '1 avocado, sliced',
            '2 tbsp tahini',
            '1 tbsp lemon juice',
            'Olive oil, salt, pepper'
        ],
        'instructions': [
            'Cook quinoa in water/broth for 15 minutes until fluffy',
            'Roast sweet potato cubes with olive oil at 400°F for 20 minutes',
            'Sauté chickpeas with spices until crispy',
            'Massage kale with olive oil and lemon',
            'Mix tahini with lemon juice and water for dressing',
            'Assemble bowl with quinoa base, add all toppings',
            'Drizzle with tahini dressing and enjoy'
        ],
        'tags': ['vegetarian', 'high-protein', 'low-gi', 'anti-inflammatory'],
        'difficulty': 'easy'
    },
    'veggie-omelet': {
        'name': 'Veggie Omelet Power Bowl',
        'emoji': '🍳',
        'description': 'Protein-packed breakfast with spinach, mushrooms, and avocado',
        'prep_time': '10 mins',
        'cook_time': '5 mins',
        'servings': 1,
        'calories': 350,
        'protein': 24,
        'carbs': 18,
        'fats': 22,
        'fiber': 8,
        'benefits': 'Rich in protein and healthy fats to keep you full and support hormone production.',
        'ingredients': [
            '3 large eggs',
            '1 cup fresh spinach',
            '1/2 cup mushrooms, sliced',
            '1/4 onion, diced',
            '1/2 avocado, sliced',
            '2 tbsp feta cheese (optional)',
            '1 tbsp olive oil',
            'Salt, pepper, herbs to taste'
        ],
        'instructions': [
            'Whisk eggs with salt and pepper',
            'Heat olive oil in non-stick pan',
            'Sauté mushrooms and onions until soft',
            'Add spinach and cook until wilted',
            'Pour eggs over vegetables',
            'Cook until edges set, then fold omelet',
            'Top with avocado and feta',
            'Serve immediately'
        ],
        'tags': ['high-protein', 'quick', 'gluten-free', 'keto-friendly'],
        'difficulty': 'easy'
    },
    'baked-salmon': {
        'name': 'Baked Salmon with Veggies',
        'emoji': '🐟',
        'description': 'Omega-3 rich salmon with roasted Brussels sprouts and sweet potato',
        'prep_time': '15 mins',
        'cook_time': '25 mins',
        'servings': 2,
        'calories': 450,
        'protein': 35,
        'carbs': 32,
        'fats': 20,
        'fiber': 8,
        'benefits': 'Packed with omega-3 fatty acids that reduce inflammation and support hormone balance.',
        'ingredients': [
            '2 salmon fillets (6 oz each)',
            '2 cups Brussels sprouts, halved',
            '1 large sweet potato, cubed',
            '3 cloves garlic, minced',
            '2 tbsp olive oil',
            '1 lemon, sliced',
            'Fresh dill or parsley',
            'Salt, pepper, paprika'
        ],
        'instructions': [
            'Preheat oven to 400°F',
            'Toss vegetables with olive oil, garlic, salt, and pepper',
            'Spread vegetables on baking sheet',
            'Season salmon with salt, pepper, and paprika',
            'Place salmon on vegetables',
            'Top with lemon slices and herbs',
            'Bake for 20-25 minutes until salmon flakes easily',
            'Serve hot with extra lemon'
        ],
        'tags': ['high-protein', 'omega-3', 'anti-inflammatory', 'gluten-free'],
        'difficulty': 'medium'
    }
}




# ============================================
# GEMMA API INTEGRATION - FIXED WITH STREAMING
# ============================================
def call_gemma_api_stream(prompt, max_tokens=500):
    """Call Gemma API via Ollama with streaming (like chatbot)"""
    try:
        payload = {
            "model": "gemma3:12b",
            "prompt": prompt,
            "stream": True,  # Enable streaming
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": max_tokens
            }
        }
        
        logger.info(f"Calling Gemma API at {GEMMA_API}")
        response = requests.post(
            GEMMA_API,
            json=payload,
            stream=True,
            timeout=60
        )
        
        if response.status_code == 200:
            full_response = []
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line.decode("utf-8"))
                    if "response" in data:
                        full_response.append(data["response"])
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
            
            result = "".join(full_response).strip()
            logger.info(f"Gemma API response length: {len(result)}")
            return result
        else:
            logger.error(f"Gemma API error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Gemma API timeout after 60 seconds")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Gemma API connection error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Gemma API unexpected error: {str(e)}")
        return None


def generate_meal_recommendation(user_data, meal_type):
    """Generate personalized meal recommendation using Gemma"""
    
    prompt = f"""You are a PCOS nutrition expert. Create a {meal_type} recipe recommendation.

User Profile:
- Diet: {user_data.get('diet_description', 'Not specified')}
- Activity Level: {user_data.get('activity_frequency', 'Moderate')}
- Primary Concerns: {user_data.get('primary_concerns', 'General PCOS management')}
- Stress Level: {user_data.get('stress_level', 'Moderate')}

Create a PCOS-friendly {meal_type} recipe with:
1. Recipe name
2. Brief description (1 sentence)
3. Prep time
4. Calories
5. Why it's good for PCOS (1 sentence)

Format your response as JSON:
{{
    "name": "Recipe Name",
    "description": "Brief description",
    "prep_time": "15 mins",
    "calories": 350,
    "benefits": "PCOS benefit",
    "ingredients": ["ingredient 1", "ingredient 2"],
    "instructions": "Quick instructions"
}}

Keep it concise and practical."""

    response = call_gemma_api_stream(prompt, max_tokens=400)
    
    if response:
        try:
            # Extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                parsed = json.loads(json_str)
                logger.info(f"Successfully parsed AI response for {meal_type}")
                return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemma response as JSON: {str(e)}")
    
    # Fallback recipe
    logger.warning(f"Using fallback recipe for {meal_type}")
    return {
        "name": f"Healthy {meal_type.title()}",
        "description": "A balanced, PCOS-friendly meal",
        "prep_time": "20 mins",
        "calories": 400,
        "benefits": "Supports hormone balance and energy",
        "ingredients": ["Whole grains", "Lean protein", "Vegetables"],
        "instructions": "Combine ingredients and cook as desired"
    }


def generate_daily_nutrition_tip(user_data):
    """Generate personalized nutrition tip using Gemma"""
    
    prompt = f"""You are a PCOS nutrition expert. Give ONE practical nutrition tip.

User Context:
- Current Diet: {user_data.get('diet_description', 'Not specified')}
- Stress Level: {user_data.get('stress_level', 'Moderate')}
- Primary Concerns: {user_data.get('primary_concerns', 'General health')}

Provide a single, actionable nutrition tip (max 2 sentences) that addresses their specific situation and PCOS management."""

    response = call_gemma_api_stream(prompt, max_tokens=150)
    
    if response:
        # Clean up response
        tip = response.strip().replace('\n', ' ')
        # Take first 2 sentences
        sentences = tip.split('.')[:2]
        return '.'.join(sentences) + '.'
    
    return "Focus on low-GI foods and balanced meals to support stable blood sugar levels throughout the day."


# ============================================
# NUTRITION CALCULATOR
# ============================================
def calculate_nutrition_metrics(pcos_data):
    """Calculate personalized nutrition metrics based on user data"""
    
    # Base calorie goal (can be customized based on user goals)
    base_calories = 1800
    
    # Adjust based on activity level
    activity_multipliers = {
        'daily': 1.2,
        '3-4 times': 1.15,
        '1-2 times': 1.05,
        'rarely': 1.0
    }
    
    multiplier = 1.0
    if pcos_data.activity_frequency:
        activity_lower = pcos_data.activity_frequency.lower()
        for key, value in activity_multipliers.items():
            if key in activity_lower:
                multiplier = value
                break
    
    calorie_goal = int(base_calories * multiplier)
    
    # Macronutrient goals (PCOS-friendly ratios)
    protein_goal = int((calorie_goal * 0.30) / 4)  # 30% of calories, 4 cal/g
    carbs_goal = int((calorie_goal * 0.40) / 4)    # 40% of calories, 4 cal/g
    fat_goal = int((calorie_goal * 0.30) / 9)      # 30% of calories, 9 cal/g
    
    # Current intake (mock data - in real app, track from meal logs)
    current_calories = int(calorie_goal * 0.75)
    current_protein = int(protein_goal * 0.78)
    current_carbs = int(carbs_goal * 0.80)
    
    return {
        'calorie_goal': calorie_goal,
        'current_calories': current_calories,
        'protein_goal': protein_goal,
        'current_protein': current_protein,
        'carbs_goal': carbs_goal,
        'current_carbs': current_carbs,
        'fat_goal': fat_goal,
        'water_goal': 8,
        'water_current': 6
    }


# ============================================
# MAIN NUTRITION VIEW
# ============================================
def nutrition(request):
    """Dynamic nutrition guide with real user data and AI recommendations"""
    user, redirect_url = get_authenticated_user(request)
    if not user:
        return redirect(redirect_url)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
    except PCOSUserData.DoesNotExist:
        return redirect("/onboarding/")
    
    # Calculate nutrition metrics
    nutrition_metrics = calculate_nutrition_metrics(pcos_data)
    
    # Get today's water intake
    today = timezone.now().date()
    water_log, _ = WaterIntakeLog.objects.get_or_create(
        user=user,
        date=today,
        defaults={'glasses': 0}
    )
    nutrition_metrics['water_current'] = water_log.glasses
    
    # Prepare user data for AI
    user_context = {
        'diet_description': pcos_data.diet_description or 'Not specified',
        'activity_frequency': pcos_data.activity_frequency or 'Moderate',
        'primary_concerns': pcos_data.primary_concerns or 'General PCOS management',
        'stress_level': pcos_data.stress_level or 'Moderate',
        'pcos_status': pcos_data.pcos_status or 'Managing'
    }
    
    # Get saved meal plans (if any)
    saved_meals = MealPlan.objects.filter(user=user, is_favorite=True).order_by('-created_at')[:6]
    
    # Calculate nutrition score
    nutrition_score = calculate_nutrition_score(pcos_data)
    
    context = {
        'user_name': user.username,
        'calories_current': nutrition_metrics['current_calories'],
        'calories_goal': nutrition_metrics['calorie_goal'],
        'protein_current': nutrition_metrics['current_protein'],
        'protein_goal': nutrition_metrics['protein_goal'],
        'carbs_current': nutrition_metrics['current_carbs'],
        'carbs_goal': nutrition_metrics['carbs_goal'],
        'water_current': nutrition_metrics['water_current'],
        'water_goal': nutrition_metrics['water_goal'],
        'nutrition_score': nutrition_score,
        'diet_description': pcos_data.diet_description or 'Not specified',
        'saved_meals': saved_meals,
        'user_context': json.dumps(user_context),
        'today': datetime.now().strftime('%B %d, %Y')
    }
    
    return render(request, "nutrition.html", context)


def calculate_nutrition_score(pcos_data):
    """Calculate overall nutrition score (0-100)"""
    if not pcos_data.diet_description:
        return 75
    
    diet_lower = pcos_data.diet_description.lower()
    
    positive_keywords = [
        'balanced', 'healthy', 'nutritious', 'whole foods', 'vegetables',
        'fruits', 'lean protein', 'fiber', 'clean', 'organic'
    ]
    negative_keywords = [
        'processed', 'junk', 'fast food', 'sugar', 'refined',
        'irregular', 'skip meals', 'unhealthy', 'fried'
    ]
    
    positive_count = sum(1 for keyword in positive_keywords if keyword in diet_lower)
    negative_count = sum(1 for keyword in negative_keywords if keyword in diet_lower)
    
    base_score = 75
    score = base_score + (positive_count * 3) - (negative_count * 5)
    
    return max(50, min(95, score))


# ============================================
# API ENDPOINTS
# ============================================

@require_POST
@csrf_exempt
def generate_meal_plan(request):
    """Generate AI-powered meal recommendation"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        meal_type = data.get('meal_type', 'lunch')
        
        pcos_data = PCOSUserData.objects.get(user=user)
        
        user_context = {
            'diet_description': pcos_data.diet_description or 'Balanced diet',
            'activity_frequency': pcos_data.activity_frequency or 'Moderate',
            'primary_concerns': pcos_data.primary_concerns or 'General health',
            'stress_level': pcos_data.stress_level or 'Moderate'
        }
        
        # Generate recommendation using Gemma
        meal_data = generate_meal_recommendation(user_context, meal_type)
        
        logger.info(f"Generated {meal_type} recommendation for {user.username}")
        
        return JsonResponse({
            "status": "success",
            "meal": meal_data
        })
        
    except PCOSUserData.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "User data not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error generating meal plan: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Failed to generate meal plan"
        }, status=500)


@require_POST
@csrf_exempt
def save_meal_plan(request):
    """Save a meal plan as favorite"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        
        meal_plan = MealPlan.objects.create(
            user=user,
            name=data.get('name'),
            description=data.get('description'),
            meal_type=data.get('meal_type', 'lunch'),
            ingredients=', '.join(data.get('ingredients', [])),
            instructions=data.get('instructions', ''),
            calories=data.get('calories'),
            protein=data.get('protein'),
            carbs=data.get('carbs'),
            fats=data.get('fats'),
            is_pcos_friendly=True,
            is_favorite=True
        )
        
        logger.info(f"Meal plan saved for user: {user.username}")
        
        return JsonResponse({
            "status": "success",
            "message": "Meal plan saved successfully",
            "meal_id": meal_plan.id
        })
        
    except Exception as e:
        logger.error(f"Error saving meal plan: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Failed to save meal plan"
        }, status=500)


@require_GET
def get_nutrition_tip(request):
    """Get daily personalized nutrition tip"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        pcos_data = PCOSUserData.objects.get(user=user)
        
        user_context = {
            'diet_description': pcos_data.diet_description or 'Balanced diet',
            'stress_level': pcos_data.stress_level or 'Moderate',
            'primary_concerns': pcos_data.primary_concerns or 'General health'
        }
        
        # Generate tip using Gemma
        tip = generate_daily_nutrition_tip(user_context)
        
        return JsonResponse({
            "status": "success",
            "tip": tip
        })
        
    except PCOSUserData.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "User data not found"
        }, status=404)
    except Exception as e:
        logger.error(f"Error generating nutrition tip: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Failed to generate tip"
        }, status=500)


@require_POST
@csrf_exempt
def log_water_intake(request):
    """Log water intake"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        data = json.loads(request.body)
        glasses = data.get('glasses', 1)
        
        # Store in session for now (in production, use database)
        today = datetime.now().date().isoformat()
        
        if 'water_intake' not in request.session:
            request.session['water_intake'] = {}
        
        current = request.session['water_intake'].get(today, 0)
        request.session['water_intake'][today] = min(current + glasses, 10)
        request.session.modified = True
        
        return JsonResponse({
            "status": "success",
            "total": request.session['water_intake'][today]
        })
        
    except Exception as e:
        logger.error(f"Error logging water intake: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Failed to log water intake"
        }, status=500)


@require_GET
def get_meal_history(request):
    """Get user's saved meal plans"""
    user, _ = get_authenticated_user(request)
    if not user:
        return JsonResponse({"status": "error", "message": "Not authenticated"}, status=401)
    
    try:
        meals = MealPlan.objects.filter(user=user).order_by('-created_at')[:20]
        
        meal_data = []
        for meal in meals:
            meal_data.append({
                'id': meal.id,
                'name': meal.name,
                'description': meal.description,
                'meal_type': meal.meal_type,
                'calories': meal.calories,
                'protein': meal.protein,
                'carbs': meal.carbs,
                'is_favorite': meal.is_favorite,
                'created_at': meal.created_at.isoformat()
            })
        
        return JsonResponse({
            "status": "success",
            "meals": meal_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching meal history: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": "Failed to fetch meal history"
        }, status=500)