from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import UserAccount, EmailOTP, SessionStore
from .utils import generate_otp, send_otp_email
from django.utils import timezone
import uuid
from django.views.decorators.cache import never_cache
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


from django.http import JsonResponse

def signup_view(request):
    if request.session.get("session_id"):
        try:
            session = SessionStore.objects.get(session_id=request.session["session_id"])
            if not session.is_guest:
                return redirect("home")
        except SessionStore.DoesNotExist:
            pass

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Email already exists → return JSON if AJAX
        if UserAccount.objects.filter(email=email).exists():
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": "Email already registered"}, status=400)
            return render(request, "auth/signup.html", {"error": "Email already registered"})

        # Normal signup flow
        otp = generate_otp(email)
        send_otp_email(email, otp)
        request.session["temp_user"] = {"username": username, "email": email, "password": password}
        return redirect("verify_otp")

    return render(request, "auth/signup.html")



@csrf_exempt
def resend_otp_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    temp_user = request.session.get("temp_user")
    if not temp_user:
        return JsonResponse({"success": False, "error": "No signup session found"}, status=400)

    email = temp_user["email"]
    otp = generate_otp(email)
    send_otp_email(email, otp)

    return JsonResponse({"success": True, "message": "New OTP sent to your email!"})



@never_cache
@never_cache
def verify_otp_view(request):
    session_id = request.session.get("session_id")
    if session_id:
        try:
            session = SessionStore.objects.get(session_id=session_id)
            if session.user and not session.is_guest:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"success": True, "redirect": "/"})
                return redirect("home")
        except SessionStore.DoesNotExist:
            pass

    temp_user = request.session.get("temp_user")  # ✅ Get temp user
    email = temp_user["email"] if temp_user else None  # ✅ Extract email

    if request.method == "POST":
        otp = request.POST.get("otp")
        if not temp_user:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": "No signup session found"})
            return render(request, "auth/verify_otp.html", {"error": "No signup session found"})

        otp_obj = EmailOTP.objects.filter(
            email=temp_user["email"], otp=otp, is_used=False
        ).last()

        if not otp_obj:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": "Invalid or expired OTP"})
            return render(request, "auth/verify_otp.html", {
                "error": "Invalid or expired OTP",
                "email": email,   # ✅ Keep email visible
            })

        # Mark OTP as used
        otp_obj.is_used = True
        otp_obj.save()

        # Save verified user
        user = UserAccount(
            username=temp_user["username"],
            email=temp_user["email"],
        )
        user.set_password(temp_user["password"])
        user.is_verified = True
        user.save()

        # Clear temp session
        if "temp_user" in request.session:
            del request.session["temp_user"]

        # Create authenticated session
        session = SessionStore.objects.create(
            user=user,
            is_guest=False,
            data={"username": user.username, "email": user.email}
        )
        request.session["session_id"] = str(session.session_id)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": True,
                "message": "Email verified successfully!",
                "redirect": "/onboarding/"
            })

        return redirect("home")

    # ✅ Always pass email into context when rendering
    return render(request, "auth/verify_otp.html", {"email": email})


@csrf_exempt
@never_cache
# Login View
def login_view(request):
    # 🚨 Prevent already logged-in users from opening the login page
    if request.session.get("session_id"):
        try:
            session = SessionStore.objects.get(session_id=request.session["session_id"])
            if not session.is_guest:
                return redirect("home")  # already logged in
        except SessionStore.DoesNotExist:
            pass

    if request.method == "POST":
        email_or_username = request.POST.get("email_or_username")
        password = request.POST.get("password")

        # 🔹 Find user by email or username
        try:
            user = UserAccount.objects.get(email=email_or_username)
        except UserAccount.DoesNotExist:
            try:
                user = UserAccount.objects.get(username=email_or_username)
            except UserAccount.DoesNotExist:
                return render(request, "auth/login.html", {"error": "Invalid credentials"})

        # 🔹 Check password
        if not user.check_password(password):
            return render(request, "auth/login.html", {"error": "Invalid credentials"})

        # 🔹 Create session (authenticated)
        session = SessionStore.objects.create(
            user=user,
            is_guest=False,
            data={"username": user.username, "email": user.email}
        )
        request.session["session_id"] = str(session.session_id)

        return redirect("home")

    return render(request, "auth/login.html")





def google_login_view(request):
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_LOGIN_REDIRECT_URI}"  # 👈 separate redirect
        "&response_type=code"
        "&scope=openid%20email%20profile"
    )
    return redirect(google_auth_url)


def google_login_callback_view(request):
    code = request.GET.get("code")
    if not code:
        return render(request, "auth/login.html", {"error": "Google login failed."})

    # Get token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    token_info = requests.post(token_url, data=data).json()
    access_token = token_info.get("access_token")

    if not access_token:
        return render(request, "auth/login.html", {"error": "Google authentication failed."})

    # Get user info
    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    email = user_info.get("email")

    try:
        user = UserAccount.objects.get(email=email)
    except UserAccount.DoesNotExist:
        return render(request, "auth/login.html", {
            "error": "No account found. Please sign up with Google first."
        })

    # Create session
    session = SessionStore.objects.create(
        user=user, is_guest=False, data={"username": user.username, "email": user.email}
    )
    request.session["session_id"] = str(session.session_id)

    return redirect("home")




def google_signup_view(request):
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_SIGNUP_REDIRECT_URI}"  # 👈 separate redirect
        "&response_type=code"
        "&scope=openid%20email%20profile"
    )
    return redirect(google_auth_url)


def google_signup_callback_view(request):
    code = request.GET.get("code")
    if not code:
        return render(request, "auth/signup.html", {"error": "Google signup failed."})

    # Get token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_SIGNUP_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    token_info = requests.post(token_url, data=data).json()
    access_token = token_info.get("access_token")

    if not access_token:
        return render(request, "auth/signup.html", {"error": "Google authentication failed."})

    # Get user info
    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    email = user_info.get("email")
    username = user_info.get("name")

    if not email:
        return render(request, "auth/signup.html", {"error": "No email found in Google account."})

    # 🚨 If user already exists → error
    if UserAccount.objects.filter(email=email).exists():
        return render(request, "auth/signup.html", {
            "error": "Account already exists. Please log in with Google."
        })

    # ✅ Create new account
    user = UserAccount.objects.create(email=email, username=username, is_verified=True)

    # Create session
    session = SessionStore.objects.create(
        user=user, is_guest=False, data={"username": user.username, "email": user.email}
    )
    request.session["session_id"] = str(session.session_id)

    return redirect("onboarding") # 👈 redirect to onboarding


def home_view(request):
    session_id = request.session.get("session_id")
    if not session_id:
        # Create guest session
        session = SessionStore.objects.create(is_guest=True, data={"role": "guest"})
        request.session["session_id"] = str(session.session_id)
        return render(request, "user/home_guest.html")

    try:
        session = SessionStore.objects.get(session_id=session_id)
    except SessionStore.DoesNotExist:
        return render(request, "user/home_guest.html")

    if session.is_guest:
        return render(request, "user/home_guest.html")
    else:
        return render(request, "user/home_auth.html", {"user": session.user})


def logout_view(request):
    session_id = request.session.get("session_id")
    if session_id:
        try:
            from .models import SessionStore
            SessionStore.objects.filter(session_id=session_id).delete()
        except:
            pass
        del request.session["session_id"]

    return redirect("home")

from .decorators import session_login_required

@session_login_required
def home_view_test(request):
    user = request.custom_user  # ✅ Access logged-in user
    return render(request, "user/home_auth.html", {"user": user})


def articles(request):
    return render(request,"user/articles.html")

def info(request):
    return render(request,"user/info.html")