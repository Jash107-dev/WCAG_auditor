from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils import timezone
from core.models import PasswordResetToken
import random
import time


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        # Django auth uses username — look up user by email
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, "No account found with that email address.")
            return render(request, "auth/login.html", {"email": email})

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next", "home")
            return redirect(next_url)
        else:
            messages.error(request, "Incorrect password. Please try again.")
            return render(request, "auth/login.html", {"email": email})

    return render(request, "auth/login.html")


def send_otp_view(request):
    """Send a 6-digit OTP to the given email address."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    email = request.POST.get("email", "").strip().lower()
    if not email:
        return JsonResponse({"error": "Email is required."}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "An account with this email already exists."}, status=400)

    otp = str(random.randint(100000, 999999))
    request.session["otp_code"] = otp
    request.session["otp_email"] = email
    request.session["otp_created_at"] = time.time()
    print(f"[OTP DEBUG] Email: {email} | OTP: {otp}")  # visible in runserver terminal

    try:
        # Render HTML email template
        html_body = render_to_string("email/otp.html", {"otp": otp})
        text_body = (
            f"Your WCAG Auditor verification code is: {otp}\n\n"
            f"This code expires in 5 minutes.\n\n"
            f"If you did not request this, please ignore this email."
        )

        msg = EmailMultiAlternatives(
            subject="Your WCAG Auditor verification code",
            body=text_body,
            from_email=f"WCAG Auditor <{settings.EMAIL_HOST_USER}>",
            to=[email],
            reply_to=[settings.EMAIL_HOST_USER],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)

        import logging
        logging.getLogger(__name__).info(f"OTP sent to {email}")
        return JsonResponse({"success": True, "message": "OTP sent to your email."})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Email send failed: {e}")
        print(f"[OTP EMAIL ERROR] {e}")
        return JsonResponse({"error": f"Failed to send email: {str(e)}"}, status=500)


def verify_otp_view(request):
    """Verify the OTP entered by the user."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    entered_otp = request.POST.get("otp", "").strip()
    stored_otp = request.session.get("otp_code")
    stored_email = request.session.get("otp_email")
    created_at = request.session.get("otp_created_at", 0)

    if not stored_otp or not stored_email:
        return JsonResponse({"error": "No OTP found. Please request a new one."}, status=400)

    expiry = getattr(settings, "OTP_EXPIRY_SECONDS", 300)
    if time.time() - created_at > expiry:
        # Clear expired OTP
        for key in ("otp_code", "otp_email", "otp_created_at"):
            request.session.pop(key, None)
        return JsonResponse({"error": "OTP has expired. Please request a new one."}, status=400)

    if entered_otp != stored_otp:
        return JsonResponse({"error": "Incorrect OTP. Please try again."}, status=400)

    # Mark email as verified in session
    request.session["otp_verified_email"] = stored_email
    for key in ("otp_code", "otp_created_at"):
        request.session.pop(key, None)

    return JsonResponse({"success": True, "message": "Email verified successfully."})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password1 = request.POST.get("password", "")
        password2 = request.POST.get("confirm_password", "")
        terms = request.POST.get("terms")

        # Validation
        if not terms:
            messages.error(request, "You must agree to the Terms of Service.")
            return render(request, "auth/register.html", {"full_name": full_name, "email": email})

        # Check OTP was verified
        verified_email = request.session.get("otp_verified_email", "")
        if verified_email != email:
            messages.error(request, "Please verify your email address with OTP before registering.")
            return render(request, "auth/register.html", {"full_name": full_name, "email": email})

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "auth/register.html", {"full_name": full_name, "email": email})

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/register.html", {"full_name": full_name, "email": email})

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, "auth/register.html", {"full_name": full_name, "email": email})

        # Create user — use email as username too
        username = email
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
        )

        # Save full name
        name_parts = full_name.split(" ", 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        user.save()

        # Auto login after register
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.pop("otp_verified_email", None)
        request.session.pop("otp_email", None)
        messages.success(request, f"Welcome, {user.first_name}! Your account has been created.")
        return redirect("home")

    return render(request, "auth/register.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        # Always show success to prevent email enumeration
        try:
            user = User.objects.get(email=email)

            # Invalidate any existing unused tokens for this user
            PasswordResetToken.objects.filter(user=user, used=False).update(used=True)

            token = get_random_string(48)
            PasswordResetToken.objects.create(user=user, token=token)

            reset_url = request.build_absolute_uri(f"/reset-password/{token}/")

            html_body = render_to_string("email/reset_password.html", {
                "user": user,
                "reset_url": reset_url,
            })
            text_body = (
                f"Hi {user.first_name or user.username},\n\n"
                f"Click the link below to reset your WCAG Auditor password:\n\n"
                f"{reset_url}\n\n"
                f"This link expires in 30 minutes.\n\n"
                f"If you did not request this, please ignore this email."
            )

            msg = EmailMultiAlternatives(
                subject="Reset your WCAG Auditor password",
                body=text_body,
                from_email=f"WCAG Auditor <{settings.EMAIL_HOST_USER}>",
                to=[email],
                reply_to=[settings.EMAIL_HOST_USER],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
            print(f"[RESET] Link sent to {email}: {reset_url}")

        except User.DoesNotExist:
            pass  # Don't reveal whether email exists

        messages.success(request, "If an account exists with that email, a reset link has been sent.")
        return redirect("forgot_password")

    return render(request, "auth/forgot_password.html")


def reset_password_view(request, token):
    try:
        reset_token = PasswordResetToken.objects.select_related("user").get(token=token)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "This reset link is invalid or has already been used.")
        return redirect("forgot_password")

    if not reset_token.is_valid():
        messages.error(request, "This reset link has expired. Please request a new one.")
        return redirect("forgot_password")

    if request.method == "POST":
        password1 = request.POST.get("password", "")
        password2 = request.POST.get("confirm_password", "")

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "auth/reset_password.html", {"token": token})

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/reset_password.html", {"token": token})

        user = reset_token.user
        user.set_password(password1)
        user.save()

        # Mark token as used
        reset_token.used = True
        reset_token.save()

        messages.success(request, "Password reset successfully. You can now sign in.")
        return redirect("login")

    return render(request, "auth/reset_password.html", {"token": token})


def terms_view(request):
    return render(request, "auth/terms.html")


def privacy_view(request):
    return render(request, "auth/privacy.html")


def test_wcag_page(request):
    return render(request, "test_wcag.html")
