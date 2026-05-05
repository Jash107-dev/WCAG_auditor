from core.models import Page, Rule, Issue
from analyzer.checks import run_all_checks

def get_or_create_rule(wcag_id):
    rule = Rule.objects.filter(wcag_id=wcag_id).first()
    if not rule:
        defaults = {
            '1.1.1': ('Non-text Content', 'A', 'Perceivable'),
            '3.3.2': ('Labels or Instructions', 'A', 'Understandable'),
            '1.3.1': ('Info and Relationships', 'A', 'Perceivable'),
            '3.1.1': ('Language of Page', 'A', 'Understandable'),
            '2.4.4': ('Link Purpose (In Context)', 'A', 'Operable'),
        }

        title, level, category = defaults.get(wcag_id, (f"Rule {wcag_id}", "A", "General"))

        rule = Rule.objects.create(
            wcag_id=wcag_id,
            title=title,
            level=level,
            category=category,
            check_type="deterministic",
            description="Dynamically created rule",
            logic="Automated deterministic check",
            fix_suggestion="Follow issue recommendation"
        )
    return rule

def analyze_page(page_id):
    try:
        page = Page.objects.get(id=page_id)
    except Page.DoesNotExist:
        print(f"Page with ID {page_id} not found.")
        return False

    print(f"Analyzing page: {page.url}")

    Issue.objects.filter(page=page).delete()

    issues_found = run_all_checks(page.html_snapshot)

    for issue_data in issues_found:
        rule = get_or_create_rule(issue_data['wcag_id'])

        full_message = f"{issue_data['message']}\nElement Snippet: {issue_data['element']}"

        Issue.objects.create(
            page=page,
            rule=rule,
            severity=issue_data['severity'],
            message=full_message,
            fix=issue_data['fix']
        )

    page.status = "analyzed"
    page.save()
    print(f"Finished analyzing {page.url}. Found {len(issues_found)} issues.")
    return True

def analyze_project(project_id, async_mode=False):
    from analyzer.tasks import async_analyze_page

    pages = Page.objects.filter(project_id=project_id, status="done")
    count = 0
    for page in pages:
        if async_mode:
            async_analyze_page.delay(page.id)
        else:
            analyze_page(page.id)
        count += 1

    mode_str = "asynchronously" if async_mode else "synchronously"
    print(f"Completed dispatching analysis {mode_str} for project {project_id}. Pages: {count}")
