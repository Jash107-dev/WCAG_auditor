"""
Analysis engine — orchestrates deterministic checks + LLM enrichment.

Flow per page:
  1. Run all deterministic checks (checks.py)  → always runs
  2. Run LLM semantic checks (llm.py)          → if LLM available
  3. Enrich top issues with LLM fix suggestions → if LLM available
  4. Run readability analysis                   → if LLM available
  5. Save everything to DB
"""

import logging
from bs4 import BeautifulSoup
from core.models import Page, Rule, Issue
from analyzer.checks import run_all_checks

logger = logging.getLogger(__name__)

# Default rule metadata for rules that may not be in the DB yet
RULE_DEFAULTS = {
    "1.1.1": ("Non-text Content",           "A",  "Perceivable"),
    "1.3.1": ("Info and Relationships",     "A",  "Perceivable"),
    "2.4.2": ("Page Titled",                "A",  "Operable"),
    "2.4.4": ("Link Purpose (In Context)",  "A",  "Operable"),
    "3.1.1": ("Language of Page",           "A",  "Understandable"),
    "3.1.5": ("Reading Level",              "AAA","Understandable"),
    "3.3.2": ("Labels or Instructions",     "A",  "Understandable"),
    "4.1.2": ("Name, Role, Value",          "A",  "Robust"),
    "1.3.4": ("Orientation",                "AA", "Perceivable"),
    "1.4.3": ("Contrast (Minimum)",         "AA", "Perceivable"),
    "2.4.6": ("Headings and Labels",        "AA", "Operable"),
    "4.1.1": ("Parsing",                    "A",  "Robust"),
}

# Max issues to enrich with LLM per page (keeps analysis fast)
LLM_ENRICH_LIMIT = 5


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
    """Persist a list of issue dicts to the DB and return the saved Issue objects."""
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
    """
    Enrich saved Issue objects with LLM-generated fix suggestions.
    Also runs semantic checks and readability analysis.
    """
    from analyzer.llm import (
        enhance_issue_fix,
        run_semantic_checks,
        analyze_readability,
    )

    page.llm_status = "running"
    page.save(update_fields=["llm_status"])

    try:
        # 1. Enhance fix suggestions for top N deterministic issues
        deterministic = [
            (obj, data) for obj, data in saved_issues
            if data.get("source", "deterministic") == "deterministic"
        ]
        # Prioritise critical/serious first
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

        # 2. Run LLM semantic checks on a trimmed HTML snippet
        soup = BeautifulSoup(page.html_snapshot, "html.parser")
        # Use body content only to keep prompt size manageable
        body = soup.find("body")
        html_snippet = str(body)[:3000] if body else page.html_snapshot[:3000]

        semantic_issues = run_semantic_checks(client, html_snippet)
        if semantic_issues:
            _save_issues(page, semantic_issues, source="llm")

        # 3. Readability analysis
        text_sample = soup.get_text(separator=" ", strip=True)
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""

        readability = analyze_readability(client, page_title, text_sample)
        if readability:
            page.readability_level = readability.get("level")
            page.readability_concern = readability.get("concern")
            page.readability_improvement = readability.get("improvement")

        page.llm_status = "done"
        page.save(update_fields=[
            "llm_status", "readability_level",
            "readability_concern", "readability_improvement",
        ])
        logger.info(f"LLM enrichment complete for page {page.id}")

    except Exception as e:
        logger.error(f"LLM enrichment failed for page {page.id}: {e}")
        page.llm_status = "error"
        page.save(update_fields=["llm_status"])


def analyze_page(page_id: int, use_llm: bool = True) -> bool:
    """
    Full analysis pipeline for a single page.
    - Always runs deterministic checks
    - Runs LLM enrichment if use_llm=True and a provider is available
    """
    try:
        page = Page.objects.get(id=page_id)
    except Page.DoesNotExist:
        logger.error(f"Page {page_id} not found.")
        return False

    logger.info(f"Analyzing page: {page.url}")

    # Clear previous results
    Issue.objects.filter(page=page).delete()

    # --- Step 1: Deterministic checks ---
    issues_found = run_all_checks(page.html_snapshot)
    saved_issues = _save_issues(page, issues_found, source="deterministic")

    # Set page status based on deterministic results
    page.status = "fail" if issues_found else "pass"
    page.llm_status = "pending"
    page.save(update_fields=["status", "llm_status"])

    logger.info(f"Deterministic: {len(issues_found)} issues on {page.url}")

    # --- Step 2: LLM enrichment (optional) ---
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
    """Analyze all pages in a project."""
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
