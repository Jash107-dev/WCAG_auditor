from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
from core.models import Project, Page, Issue, Rule
from crawler.crawler import crawl
import threading
import csv
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime

@login_required
def home(request):
    if request.method == "POST":
        url = request.POST.get("url", "").strip()
        level = request.POST.get("wcag_level", "AA")
        scope = request.POST.get("scan_scope", "full")
        scan_mode = request.POST.get("scan_mode", "standard")

        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        use_llm = (scan_mode == "ai")
        new_project = Project.objects.create(domain=url, wcag_level=level, status="pending", owner=request.user)

        dispatched = _dispatch_crawl(url, new_project.id, scope, use_llm)
        if not dispatched:
            thread = threading.Thread(
                target=crawl,
                args=(url, new_project.id, scope, use_llm),
                daemon=True
            )
            thread.start()

        return redirect("dashboard", project_id=new_project.id)
    return render(request, "core/home.html")


def _dispatch_crawl(url, project_id, scope, use_llm):
    try:
        from crawler.tasks import crawl_website_task
        crawl_website_task.delay(url, project_id, scope, use_llm)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Celery unavailable ({e}), falling back to thread"
        )
        return False

def crawl_status(request, project_id):
    try:
        proj = Project.objects.get(id=project_id)
        return JsonResponse({
            "status": proj.status,
            "current_page": proj.current_page or "",
            "pages_crawled": proj.pages_crawled,
            "total_pages": proj.total_pages,
            "stop_requested": proj.stop_requested,
        })
    except:
        return JsonResponse({"status": "error", "current_page": "", "pages_crawled": 0, "total_pages": 0})


def stop_crawl(request, project_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        proj = Project.objects.get(id=project_id)
        proj.stop_requested = True
        proj.save(update_fields=["stop_requested"])
        return JsonResponse({"status": "stop_requested", "project_id": project_id})
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found"}, status=404)

@login_required
def dashboard(request, project_id):
    proj = Project.objects.get(id=project_id)
    all_pages = proj.page_set.all()
    total_pages = all_pages.count()
    all_issues = Issue.objects.filter(page__project=proj)
    total_issues = all_issues.count()

    critical_page_ids = set(
        all_issues.filter(severity="critical")
        .values_list("page_id", flat=True).distinct()
    )
    any_issue_page_ids = set(
        all_issues.values_list("page_id", flat=True).distinct()
    )

    non_compliant_pages = len(critical_page_ids)
    partial_pages = len(any_issue_page_ids - critical_page_ids)
    compliant_pages = total_pages - non_compliant_pages - partial_pages
    compliant_pages = max(0, compliant_pages)
    pages_with_issues = all_pages.filter(status="fail").count()

    if total_pages > 0:
        percent_compliant = round((compliant_pages / total_pages) * 100, 2)
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
    recent_scans = Project.objects.filter(owner=request.user).order_by("-created_at")[:5]
    if percent_compliant >= 80:
        ada_status = "compliant"
        ada_msg = "This site aligns with ADA accessibility expectations based on WCAG " + proj.wcag_level + " checks."
    else:
        ada_status = "partial"
        ada_msg = "This site is PARTIALLY compliant with WCAG " + proj.wcag_level + ". " + str(pages_with_issues) + " pages have accessibility issues that need attention."
    return render(request, "core/dashboard.html", {"project": proj, "pages": all_pages, "total_pages": total_pages, "compliant_pages": compliant_pages, "pages_with_issues": pages_with_issues, "non_compliant_pages": non_compliant_pages, "total_issues": total_issues, "percent_compliant": percent_compliant, "partial_pages": partial_pages, "partial_percent": partial_percent, "non_compliant_percent": non_compliant_percent, "critical_issues": critical_count, "serious_issues": serious_count, "moderate_issues": moderate_count, "minor_issues": minor_count, "critical_percent": critical_pct, "serious_percent": serious_pct, "moderate_percent": moderate_pct, "minor_percent": minor_pct, "top_issues": top_issues, "recent_scans": recent_scans, "ada_status": ada_status, "ada_message": ada_msg})

@login_required
def projects_list(request):
    all_projects = Project.objects.filter(owner=request.user).order_by("-created_at")
    total_scans = all_projects.count()
    completed = all_projects.filter(status="crawled").count()
    in_progress = all_projects.filter(status__in=["pending", "crawling"]).count()
    return render(request, "core/projects.html", {
        "projects": all_projects,
        "total_scans": total_scans,
        "completed": completed,
        "in_progress": in_progress,
    })

@login_required
def scans_list(request):
    return redirect("projects")

@login_required
def pages_list(request):
    all_pages = Page.objects.filter(project__owner=request.user).select_related("project").order_by("-id")
    total = all_pages.count()
    passed = all_pages.filter(status="pass").count()
    failed = all_pages.filter(status="fail").count()
    return render(request, "core/pages.html", {"pages": all_pages, "total": total, "passed": passed, "failed": failed})

@login_required
def issues_all(request):
    all_issues = Issue.objects.filter(page__project__owner=request.user).select_related("rule", "page", "page__project").order_by("-page__project__created_at", "page__project_id", "-id")
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

@login_required
def issues_list(request, project_id):
    proj = Project.objects.get(id=project_id)
    proj_issues = Issue.objects.filter(page__project=proj).select_related("rule", "page")
    return render(request, "core/issues.html", {"project": proj, "issues": proj_issues})

@login_required
def rules_list(request):
    all_rules = Rule.objects.all().order_by("level", "wcag_id")
    return render(request, "core/rules.html", {"rules": all_rules})

@login_required
def reports_list(request):
    done_projects = Project.objects.filter(owner=request.user).exclude(status="pending").annotate(
        issue_count=Count("page__issue")
    ).order_by("-created_at")
    return render(request, "core/reports.html", {"projects": done_projects})


@login_required
def export_csv(request, project_id):
    proj = Project.objects.get(id=project_id)
    all_issues = Issue.objects.filter(page__project=proj).select_related("rule", "page")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="wcag_issues_{project_id}.csv"'

    writer = csv.writer(response)
    writer.writerow(["Page URL", "WCAG Rule ID", "Rule Title", "Level", "Severity", "Message", "Fix Recommendation"])

    for issue in all_issues:
        writer.writerow([
            issue.page.url,
            issue.rule.wcag_id,
            issue.rule.title,
            issue.rule.level,
            issue.severity,
            issue.message.replace('\n', ' '),
            issue.fix,
        ])

    return response

@login_required
def settings_page(request):
    from analyzer.llm import get_llm_client
    client = get_llm_client()
    llm_status = {
        "available": client.available,
        "provider": client.provider,
    }
    return render(request, "core/settings.html", {"llm_status": llm_status})


def llm_status_api(request):
    from analyzer.llm import get_llm_client
    client = get_llm_client()

    response = {
        "available": client.available,
        "provider": client.provider,
    }

    project_id = request.GET.get("project_id")
    if project_id:
        try:
            proj = Project.objects.get(id=project_id)
            pages = proj.page_set.all()
            total = pages.count()
            done = pages.filter(llm_status="done").count()
            running = pages.filter(llm_status="running").count()
            skipped = pages.filter(llm_status="skipped").count()
            error = pages.filter(llm_status="error").count()
            pending = pages.filter(llm_status="pending").count()
            response.update({
                "total_pages": total,
                "done": done,
                "running": running,
                "pending": pending,
                "skipped": skipped,
                "error": error,
                "percent": round((done / total * 100), 1) if total > 0 else 0,
                "finished": (done + skipped + error) == total and total > 0,
            })
        except Project.DoesNotExist:
            pass

    return JsonResponse(response)


def trigger_llm_analysis(request, project_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    proj = Project.objects.get(id=project_id)
    proj.llm_stop_requested = False
    proj.save(update_fields=["llm_stop_requested"])

    def run_llm_only():
        import logging
        logger = logging.getLogger(__name__)
        try:
            from analyzer.llm import get_llm_client
            from analyzer.engine import _run_llm_enrichment
            client = get_llm_client()
            if not client.available:
                logger.warning("LLM not available — skipping enrichment")
                return

            pages = list(proj.page_set.all())
            logger.info(f"LLM enrichment starting for {len(pages)} pages")

            for page in pages:
                proj.refresh_from_db()
                if proj.llm_stop_requested:
                    logger.info(f"LLM stop requested — halted after processing some pages")
                    break

                try:
                    existing_issues = list(
                        page.issue_set.filter(source="deterministic").select_related("rule")
                    )
                    saved = [
                        (iss, {
                            "message": iss.message,
                            "fix": iss.fix,
                            "element": "",
                            "source": "deterministic",
                        })
                        for iss in existing_issues
                    ]
                    _run_llm_enrichment(page, saved, client)
                    logger.info(f"LLM enrichment done for page {page.id}")
                except Exception as e:
                    logger.error(f"LLM enrichment failed for page {page.id}: {e}")

        except Exception as e:
            logger.error(f"LLM trigger error: {e}")

    thread = threading.Thread(target=run_llm_only, daemon=True)
    thread.start()

    page_count = proj.page_set.count()
    return JsonResponse({
        "status": "started",
        "project_id": project_id,
        "pages": page_count,
        "mode": "llm_only"
    })


def stop_llm_analysis(request, project_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        proj = Project.objects.get(id=project_id)
        proj.llm_stop_requested = True
        proj.save(update_fields=["llm_stop_requested"])
        return JsonResponse({"status": "stop_requested", "project_id": project_id})
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found"}, status=404)


def rescan_project(request, project_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        proj = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found"}, status=404)

    scan_mode = request.POST.get("scan_mode", "standard")
    use_llm = (scan_mode == "ai")

    proj.status = "pending"
    proj.pages_crawled = 0
    proj.total_pages = 0
    proj.stop_requested = False
    proj.llm_stop_requested = False
    proj.current_page = ""
    proj.save()

    proj.page_set.all().delete()

    dispatched = _dispatch_crawl(proj.domain, proj.id, "full", use_llm)
    if not dispatched:
        thread = threading.Thread(
            target=crawl,
            args=(proj.domain, proj.id, "full", use_llm),
            daemon=True
        )
        thread.start()

    return redirect("dashboard", project_id=proj.id)


def dismiss_issue(request, issue_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        issue = Issue.objects.get(id=issue_id)
        reason = request.POST.get("reason", "false_positive")
        note = request.POST.get("note", "")
        issue.dismissed = True
        issue.dismissal_reason = reason
        issue.dismissal_note = note
        issue.save(update_fields=["dismissed", "dismissal_reason", "dismissal_note"])
        return JsonResponse({"status": "dismissed", "issue_id": issue_id})
    except Issue.DoesNotExist:
        return JsonResponse({"error": "Issue not found"}, status=404)


def undismiss_issue(request, issue_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        issue = Issue.objects.get(id=issue_id)
        issue.dismissed = False
        issue.dismissal_reason = None
        issue.dismissal_note = None
        issue.save(update_fields=["dismissed", "dismissal_reason", "dismissal_note"])
        return JsonResponse({"status": "restored", "issue_id": issue_id})
    except Issue.DoesNotExist:
        return JsonResponse({"error": "Issue not found"}, status=404)
