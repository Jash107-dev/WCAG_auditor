import logging
from bs4 import BeautifulSoup
from core.models import Page, Rule, Issue
from analyzer.checks import run_all_checks

logger = logging.getLogger(__name__)

RULE_DEFAULTS = {
    "1.1.1": ("Non-text Content",           "A",  "Perceivable"),
    "1.3.1": ("Info and Relationships",     "A",  "Perceivable"),
    "1.4.3": ("Contrast (Minimum)",         "AA", "Perceivable"),
    "2.1.1": ("Keyboard",                   "A",  "Operable"),
    "2.4.1": ("Bypass Blocks",              "A",  "Operable"),
    "2.4.2": ("Page Titled",                "A",  "Operable"),
    "2.4.3": ("Focus Order",                "A",  "Operable"),
    "2.4.4": ("Link Purpose (In Context)",  "A",  "Operable"),
    "2.4.6": ("Headings and Labels",        "AA", "Operable"),
    "2.4.7": ("Focus Visible",              "AA", "Operable"),
    "3.1.1": ("Language of Page",           "A",  "Understandable"),
    "3.1.5": ("Reading Level",              "AAA","Understandable"),
    "3.3.2": ("Labels or Instructions",     "A",  "Understandable"),
    "4.1.1": ("Parsing",                    "A",  "Robust"),
    "4.1.2": ("Name, Role, Value",          "A",  "Robust"),
    "1.3.4": ("Orientation",                "AA", "Perceivable"),
}

LLM_ENRICH_LIMIT = 5


def calculate_compliance_score(issues: list) -> int:
    """
    Weighted per-page compliance score.
    Critical=-25, Serious=-15, Moderate=-5, Minor=-1. Min=0.
    """
    deductions = 0
    for issue in issues:
        sev = issue.get("severity", "minor") if isinstance(issue, dict) else getattr(issue, "severity", "minor")
        deductions += {"critical": 25, "serious": 15, "moderate": 5, "minor": 1}.get(sev, 1)
    return max(0, 100 - deductions)


def classify_page(issues: list) -> str:
    """
    Classify a page based on issue severity:
    - 'non_compliant' if any critical or serious issues
    - 'partial'       if only moderate/minor issues
    - 'compliant'     if no issues
    """
    for issue in issues:
        sev = issue.get("severity", "minor") if isinstance(issue, dict) else getattr(issue, "severity", "minor")
        if sev in ("critical", "serious"):
            return "non_compliant"
    return "partial" if issues else "compliant"


def get_or_create_rule(wcag_id: str) -> Rule:
    rule = Rule.objects.filter(wcag_id=wcag_id).first()
    if not rule:
        title, level, category = RULE_DEFAULTS.get(
            wcag_id, (f"Rule {wcag_id}", "A", "General")
        )
        rule = Rule.objects.create(
            wcag_id=wcag_id,
            title=title,
            level=level,
            category=category,
            check_type="deterministic",
            description="Dynamically created rule",
            logic="Automated check",
            fix_suggestion="Follow issue recommendation",
        )
    return rule


def _save_issues(page: Page, issues_found: list, source: str = "deterministic") -> list:
    saved = []
    for issue_data in issues_found:
        rule = get_or_create_rule(issue_data["wcag_id"])
        element_snippet = issue_data.get("element", "")
        full_message = issue_data["message"]
        if element_snippet:
            full_message += f"\nElement: {element_snippet}"

        obj = Issue.objects.create(
            page=page,
            rule=rule,
            severity=issue_data["severity"],
            message=full_message,
            fix=issue_data["fix"],
            source=issue_data.get("source", source),
        )
        saved.append((obj, issue_data))
    return saved


def _run_llm_enrichment(page: Page, saved_issues: list, client) -> None:
    from analyzer.llm import (
        enhance_issue_fix,
        run_semantic_checks,
        analyze_readability,
    )

    page.llm_status = "running"
    page.save(update_fields=["llm_status"])

    try:
        deterministic = [
            (obj, data) for obj, data in saved_issues
            if data.get("source", "deterministic") == "deterministic"
        ]
        severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
        deterministic.sort(key=lambda x: severity_order.get(x[0].severity, 9))

        for issue_obj, issue_data in deterministic[:LLM_ENRICH_LIMIT]:
            enhanced = enhance_issue_fix(
                client,
                wcag_id=issue_obj.rule.wcag_id,
                rule_title=issue_obj.rule.title,
                message=issue_data["message"],
                basic_fix=issue_data["fix"],
                element_snippet=issue_data.get("element", ""),
            )
            if enhanced:
                issue_obj.llm_analysis = enhanced
                issue_obj.save(update_fields=["llm_analysis"])

        soup = BeautifulSoup(page.html_snapshot, "html.parser")
        body = soup.find("body")
        html_snippet = str(body)[:1500] if body else page.html_snapshot[:1500]

        semantic_issues = run_semantic_checks(client, html_snippet)
        if semantic_issues:
            _save_issues(page, semantic_issues, source="llm")

        text_sample = soup.get_text(separator=" ", strip=True)
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""

        readability = analyze_readability(client, page_title, text_sample)
        if readability:
            page.readability_level = readability.get("level")
            page.readability_concern = readability.get("concern")
            page.readability_improvement = readability.get("improvement")

        all_issues = list(page.issue_set.all())
        page.compliance_score = calculate_compliance_score(all_issues)
        classification = classify_page(all_issues)
        page.status = "fail" if classification != "compliant" else "pass"

        page.llm_status = "done"
        page.save(update_fields=[
            "llm_status", "readability_level",
            "readability_concern", "readability_improvement",
            "compliance_score", "status",
        ])
        logger.info(f"LLM enrichment complete for page {page.id}")

    except Exception as e:
        logger.error(f"LLM enrichment failed for page {page.id}: {e}")
        page.llm_status = "error"
        page.save(update_fields=["llm_status"])


def analyze_page(page_id: int, use_llm: bool = True) -> bool:
    try:
        page = Page.objects.get(id=page_id)
    except Page.DoesNotExist:
        logger.error(f"Page {page_id} not found.")
        return False

    logger.info(f"Analyzing page: {page.url}")

    Issue.objects.filter(page=page).delete()

    issues_found = run_all_checks(page.html_snapshot)
    saved_issues = _save_issues(page, issues_found, source="deterministic")

    classification = classify_page(issues_found)
    page.status = "fail" if classification != "compliant" else "pass"
    page.compliance_score = calculate_compliance_score(issues_found)
    page.llm_status = "pending"
    page.save(update_fields=["status", "compliance_score", "llm_status"])

    logger.info(f"Deterministic: {len(issues_found)} issues on {page.url}")

    if use_llm:
        try:
            from analyzer.llm import get_llm_client
            client = get_llm_client()
            if client.available:
                _run_llm_enrichment(page, saved_issues, client)
            else:
                page.llm_status = "skipped"
                page.save(update_fields=["llm_status"])
                logger.info(f"LLM skipped for page {page.id} — no provider available")
        except Exception as e:
            logger.error(f"LLM setup error for page {page.id}: {e}")
            page.llm_status = "error"
            page.save(update_fields=["llm_status"])

    return True


def analyze_project(project_id: int, async_mode: bool = False, use_llm: bool = True) -> int:
    from analyzer.tasks import async_analyze_page

    pages = Page.objects.filter(project_id=project_id)
    count = 0
    for page in pages:
        if async_mode:
            async_analyze_page.delay(page.id)
        else:
            analyze_page(page.id, use_llm=use_llm)
        count += 1

    mode = "async" if async_mode else "sync"
    logger.info(f"Project {project_id}: dispatched {count} pages ({mode})")
    return count
