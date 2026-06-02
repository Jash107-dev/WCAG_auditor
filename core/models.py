from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    used = models.BooleanField(default=False)

    def is_valid(self):
        """Returns True if token is unused and less than 30 minutes old."""
        age = (timezone.now() - self.created_at).total_seconds()
        return not self.used and age <= 1800

    def __str__(self):
        return f"Reset token for {self.user.email}"


class Project(models.Model):
    domain = models.URLField()
    wcag_level = models.CharField(max_length=10)
    status = models.CharField(max_length=20, default="pending")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    current_page = models.TextField(blank=True, null=True)
    pages_crawled = models.IntegerField(default=0)
    total_pages = models.IntegerField(default=0)
    stop_requested = models.BooleanField(default=False)
    llm_stop_requested = models.BooleanField(default=False)

    def __str__(self):
        return self.domain


class Page(models.Model):
    LLM_STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("running",  "Running"),
        ("done",     "Done"),
        ("skipped",  "Skipped"),
        ("error",    "Error"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    url = models.URLField(max_length=2000)
    html_snapshot = models.TextField()
    http_status = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")
    compliance_score = models.IntegerField(default=100)
    llm_status = models.CharField(
        max_length=20, choices=LLM_STATUS_CHOICES, default="pending"
    )
    readability_level = models.CharField(max_length=20, blank=True, null=True)
    readability_concern = models.TextField(blank=True, null=True)
    readability_improvement = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.url


class Rule(models.Model):
    wcag_id = models.CharField(max_length=20)
    title = models.CharField(max_length=100)
    level = models.CharField(max_length=10)
    category = models.CharField(max_length=50)
    check_type = models.CharField(max_length=20)
    description = models.TextField()
    logic = models.TextField()
    fix_suggestion = models.TextField()

    def __str__(self):
        return self.wcag_id


class Issue(models.Model):
    ISSUE_SOURCE_CHOICES = [
        ("deterministic", "Deterministic"),
        ("llm",           "AI (LLM)"),
    ]
    DISMISSAL_REASON_CHOICES = [
        ("false_positive",  "False Positive"),
        ("not_applicable",  "Not Applicable"),
        ("accepted_risk",   "Accepted Risk"),
    ]

    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE)
    severity = models.CharField(max_length=20)
    message = models.TextField()
    fix = models.TextField()
    llm_analysis = models.TextField(blank=True, null=True)
    source = models.CharField(
        max_length=20, choices=ISSUE_SOURCE_CHOICES, default="deterministic"
    )
    dismissed = models.BooleanField(default=False)
    dismissal_reason = models.CharField(
        max_length=20, choices=DISMISSAL_REASON_CHOICES, blank=True, null=True
    )
    dismissal_note = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.message
