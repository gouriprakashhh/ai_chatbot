from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.sessions.models import Session
from django.utils import timezone
import json
import logging
from authentication.models import SessionStore, UserAccount
from .models import PCOSUserData

# Set up logging
logger = logging.getLogger(__name__)

def onboarding(request):
    session_id = request.session.get("session_id")
    user_name = None

    if not session_id:
        return redirect("login")  # Require login/session

    try:
        session = SessionStore.objects.get(session_id=session_id)
        user = session.user
        if not user:
            return redirect("login")
    except SessionStore.DoesNotExist:
        return redirect("login")

    # ✅ Check if user already completed onboarding
    if PCOSUserData.objects.filter(user=user).exists():
        return redirect("/dashboard/")  # Redirect if already completed

    user_name = user.username
    return render(request, "onboard.html", {"user_name": user_name})


@require_POST
@csrf_exempt
def save_onboarding_data(request):
    try:
        data = json.loads(request.body)

        # Extract all fields
        cycle_length = data.get("cycle_length")
        last_period_date = data.get("last_period_date")
        pcos_status = data.get("pcos_status")
        mood = data.get("mood")
        stress_level = data.get("stress_level")
        diagnosis_length = data.get("diagnosis_length")
        primary_concerns = data.get("primary_concerns")
        diet_description = data.get("diet_description")
        activity_frequency = data.get("activity_frequency")
        support_needed = data.get("support_needed")

        # Get logged-in user via session
        session_id = request.session.get("session_id")
        if not session_id:
            return JsonResponse({"status": "error", "message": "No session found"}, status=400)
        
        try:
            session = SessionStore.objects.get(session_id=session_id)
            user = session.user
            if not user:
                return JsonResponse({"status": "error", "message": "No user found in session"}, status=400)
        except SessionStore.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invalid session"}, status=400)

        # ✅ Check if user already completed onboarding
        if PCOSUserData.objects.filter(user=user).exists():
            return JsonResponse({"status": "error", "message": "Onboarding already completed"}, status=400)

        # Save to database
        PCOSUserData.objects.create(
            user=user,
            cycle_length=cycle_length,
            last_period_date=last_period_date or None,
            pcos_status=pcos_status,
            mood=mood,
            stress_level=stress_level,
            diagnosis_length=diagnosis_length,
            primary_concerns=primary_concerns,
            diet_description=diet_description,
            activity_frequency=activity_frequency,
            support_needed=support_needed,
            completed_at=timezone.now()
        )

        return JsonResponse({
            "status": "success",
            "message": "Onboarding data saved successfully",
            "redirect_url": "/dashboard/"
        })

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Internal server error: {str(e)}"}, status=500)


@require_POST
@csrf_exempt
def skip_onboarding_question(request):
    try:
        data = json.loads(request.body)
        question_key = data.get("question_key")
        
        if not request.session.session_key:
            request.session.create()
        
        # Initialize skipped questions list if it doesn't exist
        if 'skipped_questions' not in request.session:
            request.session['skipped_questions'] = []
        
        # Add the skipped question if not already there
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
    return render(request, "dashboard.html")



