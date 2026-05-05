from django.shortcuts import render, redirect
from django.db.models import Count
from django.http import JsonResponse
from core.models import Project, Page, Issue, Rule
from crawler.tasks import crawl_website_task

def home(request):
    if request.method == "POST":
        url = request.POST.get("url")
        level = request.POST.get("wcag_level")
        depth = request.POST.get("crawl_depth", "10")
        new_project = Project.objects.create(domain=url, wcag_level=level, status="pending")
        domain_only_value = request.POST.get("domain_only")
        domain_only = domain_only_value == "true"
        print(f"DEBUG: domain_only raw value = {domain_only_value}")
        print(f"DEBUG: domain_only boolean = {domain_only}")
        crawl_website_task.delay(url, new_project.id, int(depth), domain_only)
        return redirect("dashboard", project_id=new_project.id)
    return render(request, "core/home.html")

def crawl_status(request, project_id):
    try:
        proj = Project.objects.get(id=project_id)
        return JsonResponse({"status": proj.status, "current_page": proj.current_page or "", "pages_crawled": proj.pages_crawled, "total_pages": proj.total_pages})
    except:
        return JsonResponse({"status": "error", "current_page": "", "pages_crawled": 0, "total_pages": 0})

def dashboard(request, project_id):
    proj = Project.objects.get(id=project_id)
    all_pages = proj.page_set.all()
    total_pages = all_pages.count()
    compliant_pages = all_pages.filter(status="pass").count()
    pages_with_issues = all_pages.filter(status="fail").count()
    non_compliant_pages = all_pages.filter(status="fail").count()
    all_issues = Issue.objects.filter(page__project=proj)
    total_issues = all_issues.count()
    if total_pages > 0:
        percent_compliant = round((compliant_pages / total_pages) * 100, 2)
        partial_pages = total_pages - compliant_pages - non_compliant_pages
        partial_percent = round((partial_pages / total_pages) * 100, 2)
        non_compliant_percent = round((non_compliant_pages / total_pages) * 100, 2)
    else:
        percent_compliant = 0
        partial_pages = 0
        partial_percent = 0
        non_compliant_percent = 0
    critical_count = all_issues.filter(severity="critical").count()
    serious_count = all_issues.filter(severity="serious").count()
    moderate_count = all_issues.filter(severity="moderate").count()
    minor_count = all_issues.filter(severity="minor").count()
    if total_issues > 0:
        critical_pct = round((critical_count / total_issues) * 100, 2)
        serious_pct = round((serious_count / total_issues) * 100, 2)
        moderate_pct = round((moderate_count / total_issues) * 100, 2)
        minor_pct = round((minor_count / total_issues) * 100, 2)
    else:
        critical_pct = 0
        serious_pct = 0
        moderate_pct = 0
        minor_pct = 0
    top_issues = all_issues.values("page_id", "rule__wcag_id", "rule__title", "severity", "rule__logic").annotate(affected_pages=Count("page", distinct=True)).order_by("-affected_pages")[:5]
    recent_scans = Project.objects.order_by("-created_at")[:5]
    if percent_compliant >= 80:
        ada_status = "compliant"
        ada_msg = "This site aligns with ADA accessibility expectations based on WCAG " + proj.wcag_level + " checks."
    else:
        ada_status = "partial"
        ada_msg = "This site is PARTIALLY compliant with WCAG " + proj.wcag_level + ". " + str(pages_with_issues) + " pages have accessibility issues that need attention."
    return render(request, "core/dashboard.html", {"project": proj, "pages": all_pages, "total_pages": total_pages, "compliant_pages": compliant_pages, "pages_with_issues": pages_with_issues, "non_compliant_pages": non_compliant_pages, "total_issues": total_issues, "percent_compliant": percent_compliant, "partial_pages": partial_pages, "partial_percent": partial_percent, "non_compliant_percent": non_compliant_percent, "critical_issues": critical_count, "serious_issues": serious_count, "moderate_issues": moderate_count, "minor_issues": minor_count, "critical_percent": critical_pct, "serious_percent": serious_pct, "moderate_percent": moderate_pct, "minor_percent": minor_pct, "top_issues": top_issues, "recent_scans": recent_scans, "ada_status": ada_status, "ada_message": ada_msg})

def projects_list(request):
    all_projects = Project.objects.order_by("-created_at")
    return render(request, "core/projects.html", {"projects": all_projects})

def scans_list(request):
    all_scans = Project.objects.order_by("-created_at")
    total_scans = all_scans.count()
    completed = all_scans.filter(status="crawled").count()
    pending = all_scans.filter(status="pending").count()
    return render(request, "core/scans.html", {"scans": all_scans, "total_scans": total_scans, "completed": completed, "pending": pending})

def pages_list(request):
    all_pages = Page.objects.select_related("project").order_by("-id")
    total = all_pages.count()
    passed = all_pages.filter(status="pass").count()
    failed = all_pages.filter(status="fail").count()
    return render(request, "core/pages.html", {"pages": all_pages, "total": total, "passed": passed, "failed": failed})

def issues_all(request):
    all_issues = Issue.objects.select_related("rule", "page", "page__project").order_by("-page__project__created_at", "page__project_id", "-id")
    total = all_issues.count()
    critical = all_issues.filter(severity="critical").count()
    serious = all_issues.filter(severity="serious").count()
    moderate = all_issues.filter(severity="moderate").count()
    minor = all_issues.filter(severity="minor").count()
    issues_by_project = {}
    for issue in all_issues:
        project_id = issue.page.project.id
        if project_id not in issues_by_project:
            issues_by_project[project_id] = {"project": issue.page.project, "issues": []}
        issues_by_project[project_id]["issues"].append(issue)
    return render(request, "core/issues_all.html", {"issues_by_project": issues_by_project, "total": total, "critical": critical, "serious": serious, "moderate": moderate, "minor": minor})

def issues_list(request, project_id):
    proj = Project.objects.get(id=project_id)
    proj_issues = Issue.objects.filter(page__project=proj).select_related("rule", "page")
    return render(request, "core/issues.html", {"project": proj, "issues": proj_issues})

def rules_list(request):
    all_rules = Rule.objects.all().order_by("level", "wcag_id")
    return render(request, "core/rules.html", {"rules": all_rules})

def reports_list(request):
    done_projects = Project.objects.filter(status="crawled").order_by("-created_at")
    return render(request, "core/reports.html", {"projects": done_projects})

def settings_page(request):
    return render(request, "core/settings.html")
