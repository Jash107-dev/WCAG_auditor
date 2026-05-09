from bs4 import BeautifulSoup
import re

# Severity mapping: align with the DB/template expectations
# critical, serious, moderate, minor

def check_missing_alt_tags(soup):
    issues = []
    for img in soup.find_all('img'):
        if not img.has_attr('alt'):
            issues.append({
                'wcag_id': '1.1.1',
                'severity': 'critical',
                'message': 'Image is missing an alt attribute.',
                'fix': 'Add descriptive alt text or alt="" for decorative images.',
                'element': str(img)[:150]
            })
        elif img.get('alt', '').strip() == '' and img.get('role') != 'presentation':
            # alt="" is valid for decorative images, but flag if no role
            pass
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
                'severity': 'serious',
                'message': f'Form control <{control.name}> is missing a label.',
                'fix': 'Add a <label> element or use aria-label/aria-labelledby.',
                'element': str(control)[:150]
            })
    return issues


def check_heading_hierarchy(soup):
    issues = []
    headings = soup.find_all(re.compile(r'^h[1-6]$'))

    prev_level = 0
    for heading in headings:
        level = int(heading.name[1])
        if prev_level > 0 and level > prev_level + 1:
            issues.append({
                'wcag_id': '1.3.1',
                'severity': 'moderate',
                'message': f'Skipped heading level: <h{prev_level}> to <h{level}>.',
                'fix': 'Ensure heading levels are not skipped for proper document structure.',
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
            'severity': 'serious',
            'message': 'The <html> element is missing a lang attribute.',
            'fix': 'Add a lang attribute to the <html> tag (e.g., lang="en").',
            'element': '<html ...>'
        })
    return issues


def check_empty_links(soup):
    """Check for links with no accessible text (vague or empty)."""
    issues = []
    vague_texts = {'click here', 'here', 'read more', 'more', 'link', 'this', 'learn more'}
    for a in soup.find_all('a'):
        href = a.get('href', '').strip()
        # Skip anchor-only or missing href
        if not href or href == '#':
            issues.append({
                'wcag_id': '2.4.4',
                'severity': 'moderate',
                'message': 'Link has missing or placeholder href attribute.',
                'fix': 'Provide a valid URL in the href attribute.',
                'element': str(a)[:150]
            })
            continue
        # Check for vague link text
        link_text = a.get_text(strip=True).lower()
        aria_label = a.get('aria-label', '').strip()
        if not link_text and not aria_label:
            issues.append({
                'wcag_id': '2.4.4',
                'severity': 'serious',
                'message': 'Link has no accessible text.',
                'fix': 'Add descriptive text content or an aria-label to the link.',
                'element': str(a)[:150]
            })
        elif link_text in vague_texts and not aria_label:
            issues.append({
                'wcag_id': '2.4.4',
                'severity': 'minor',
                'message': f'Link text "{link_text}" is vague and not descriptive.',
                'fix': 'Use descriptive link text that explains the destination or purpose.',
                'element': str(a)[:150]
            })
    return issues


def check_empty_buttons(soup):
    """Check for buttons with no accessible label."""
    issues = []
    for btn in soup.find_all('button'):
        text = btn.get_text(strip=True)
        aria_label = btn.get('aria-label', '').strip()
        aria_labelledby = btn.get('aria-labelledby', '').strip()
        if not text and not aria_label and not aria_labelledby:
            issues.append({
                'wcag_id': '4.1.2',
                'severity': 'serious',
                'message': 'Button has no accessible label.',
                'fix': 'Add text content, aria-label, or aria-labelledby to the button.',
                'element': str(btn)[:150]
            })
    return issues


def check_missing_page_title(soup):
    """Check that the page has a non-empty <title> element."""
    issues = []
    title_tag = soup.find('title')
    if not title_tag or not title_tag.get_text(strip=True):
        issues.append({
            'wcag_id': '2.4.2',
            'severity': 'serious',
            'message': 'Page is missing a descriptive <title> element.',
            'fix': 'Add a <title> tag in the <head> that describes the page content.',
            'element': '<head>...</head>'
        })
    return issues


def check_images_with_title_only(soup):
    """Images that use title instead of alt for accessibility."""
    issues = []
    for img in soup.find_all('img'):
        if img.has_attr('alt'):
            continue
        if img.has_attr('title'):
            issues.append({
                'wcag_id': '1.1.1',
                'severity': 'moderate',
                'message': 'Image uses title attribute instead of alt for accessibility.',
                'fix': 'Replace the title attribute with a proper alt attribute.',
                'element': str(img)[:150]
            })
    return issues


def check_input_type_image(soup):
    """input[type=image] must have alt text."""
    issues = []
    for inp in soup.find_all('input', attrs={'type': 'image'}):
        if not inp.get('alt', '').strip():
            issues.append({
                'wcag_id': '1.1.1',
                'severity': 'critical',
                'message': 'Input of type "image" is missing an alt attribute.',
                'fix': 'Add an alt attribute describing the button action.',
                'element': str(inp)[:150]
            })
    return issues


def run_all_checks(html_content):
    """Run all accessibility checks and return a flat list of issue dicts."""
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    all_issues = []

    all_issues.extend(check_missing_alt_tags(soup))
    all_issues.extend(check_images_with_title_only(soup))
    all_issues.extend(check_input_type_image(soup))
    all_issues.extend(check_missing_labels(soup))
    all_issues.extend(check_heading_hierarchy(soup))
    all_issues.extend(check_missing_lang(soup))
    all_issues.extend(check_empty_links(soup))
    all_issues.extend(check_empty_buttons(soup))
    all_issues.extend(check_missing_page_title(soup))

    return all_issues
