from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages


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
        login(request, user)
        messages.success(request, f"Welcome, {user.first_name}! Your account has been created.")
        return redirect("home")

    return render(request, "auth/register.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def forgot_password_view(request):
    # Placeholder — email auth will be wired up in the next step
    return render(request, "auth/forgot_password.html")


def terms_view(request):
    return render(request, "auth/terms.html")


def privacy_view(request):
    return render(request, "auth/privacy.html")
