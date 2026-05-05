from bs4 import BeautifulSoup
import re

def check_missing_alt_tags(soup):
    issues = []
    for img in soup.find_all('img'):
        if not img.has_attr('alt'):
            issues.append({
                'wcag_id': '1.1.1',
                'severity': 'Error',
                'message': 'Image is missing an alt attribute.',
                'fix': 'Add descriptive alt text or alt="" for decorative images.',
                'element': str(img)[:150]
            })
    return issues

def check_missing_labels(soup):
    issues = []
    exclude_types = ['submit', 'button', 'hidden', 'image', 'reset']

    for control in soup.find_all(['input', 'textarea', 'select']):
        control_type = control.get('type', '').lower()
        if control.name == 'input' and control_type in exclude_types:
            continue

        is_labeled = False

        if control.has_attr('aria-label') or control.has_attr('aria-labelledby'):
            is_labeled = True

        if not is_labeled and control.find_parent('label'):
            is_labeled = True

        if not is_labeled and control.has_attr('id'):
            control_id = control['id']
            if soup.find('label', attrs={'for': control_id}):
                is_labeled = True

        if not is_labeled:
            issues.append({
                'wcag_id': '3.3.2',
                'severity': 'Error',
                'message': f'Form control <{control.name}> is missing a label.',
                'fix': 'Add a <label> element or use aria-label.',
                'element': str(control)[:150]
            })
    return issues

def check_heading_hierarchy(soup):
    issues = []
    headings = soup.find_all(re.compile('^h[1-6]$'))

    prev_level = 0
    for heading in headings:
        level = int(heading.name[1])
        if prev_level > 0 and level > prev_level + 1:
            issues.append({
                'wcag_id': '1.3.1',
                'severity': 'Warning',
                'message': f'Skipped heading level: <h{prev_level}> to <h{level}>.',
                'fix': 'Ensure heading levels are not skipped for proper structure.',
                'element': str(heading)[:150]
            })
        prev_level = level
    return issues

def check_missing_lang(soup):
    issues = []
    html_tag = soup.find('html')
    if html_tag and not html_tag.has_attr('lang'):
        issues.append({
            'wcag_id': '3.1.1',
            'severity': 'Error',
            'message': 'The <html> element is missing a lang attribute.',
            'fix': 'Add a lang attribute to the <html> tag (e.g., lang="en").',
            'element': '<html ...>'
        })
    return issues

def check_broken_links(soup):
    issues = []
    for a in soup.find_all('a'):
        href = a.get('href', '').strip()
        if not href or href == '#':
            issues.append({
                'wcag_id': '2.4.4',
                'severity': 'Warning',
                'message': 'Link has missing or placeholder href attribute.',
                'fix': 'Provide a valid URL in the href attribute.',
                'element': str(a)[:150]
            })
    return issues

def run_all_checks(html_content):
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    all_issues = []

    all_issues.extend(check_missing_alt_tags(soup))
    all_issues.extend(check_missing_labels(soup))
    all_issues.extend(check_heading_hierarchy(soup))
    all_issues.extend(check_missing_lang(soup))
    all_issues.extend(check_broken_links(soup))

    return all_issues
