from bs4 import BeautifulSoup
import re

# Severity mapping: align with the DB/template expectations
# critical, serious, moderate, minor

# ---------------------------------------------------------------------------
# Colour contrast helpers (WCAG 1.4.3)
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color):
    hex_color = hex_color.strip().lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c*2 for c in hex_color)
    if len(hex_color) != 6:
        return None
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None

def _luminance(r, g, b):
    def _c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * _c(r) + 0.7152 * _c(g) + 0.0722 * _c(b)

def _contrast_ratio(rgb1, rgb2):
    l1 = _luminance(*rgb1)
    l2 = _luminance(*rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

# Named CSS colours (common subset)
_CSS_COLORS = {
    'black': '#000000', 'white': '#ffffff', 'red': '#ff0000',
    'green': '#008000', 'blue': '#0000ff', 'yellow': '#ffff00',
    'gray': '#808080', 'grey': '#808080', 'orange': '#ffa500',
    'purple': '#800080', 'pink': '#ffc0cb', 'brown': '#a52a2a',
    'navy': '#000080', 'teal': '#008080', 'silver': '#c0c0c0',
    'lime': '#00ff00', 'maroon': '#800000', 'olive': '#808000',
    'aqua': '#00ffff', 'cyan': '#00ffff', 'fuchsia': '#ff00ff',
    'magenta': '#ff00ff', 'coral': '#ff7f50', 'salmon': '#fa8072',
    'gold': '#ffd700', 'khaki': '#f0e68c', 'indigo': '#4b0082',
    'violet': '#ee82ee', 'crimson': '#dc143c', 'turquoise': '#40e0d0',
}

def _parse_color(value):
    """Parse a CSS color string to RGB tuple or None."""
    value = value.strip().lower()
    if value in _CSS_COLORS:
        return _hex_to_rgb(_CSS_COLORS[value])
    if value.startswith('#'):
        return _hex_to_rgb(value)
    m = re.match(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None

def _extract_inline_colors(style_str):
    """Return (text_color, bg_color) from an inline style string."""
    txt, bg = None, None
    for part in style_str.split(';'):
        part = part.strip()
        if re.match(r'^color\s*:', part, re.I):
            txt = part.split(':', 1)[1].strip()
        elif re.match(r'^background-color\s*:', part, re.I) or re.match(r'^background\s*:', part, re.I):
            bg = part.split(':', 1)[1].strip()
    return txt, bg

def _parse_stylesheet_rules(css_text):
    """
    Very lightweight CSS parser — extracts selector → {color, background-color} mappings.
    Handles simple class/element selectors only.
    """
    rules = {}
    # Remove comments
    css_text = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)
    for block in re.finditer(r'([^{]+)\{([^}]*)\}', css_text):
        selectors = [s.strip() for s in block.group(1).split(',')]
        declarations = block.group(2)
        txt, bg = None, None
        for decl in declarations.split(';'):
            decl = decl.strip()
            if re.match(r'^color\s*:', decl, re.I):
                txt = decl.split(':', 1)[1].strip()
            elif re.match(r'^background-color\s*:', decl, re.I) or re.match(r'^background\s*:', decl, re.I):
                bg = decl.split(':', 1)[1].strip()
        if txt or bg:
            for sel in selectors:
                rules[sel] = {'color': txt, 'bg': bg}
    return rules


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


# ---------------------------------------------------------------------------
# Colour contrast — WCAG 1.4.3 (improved: inline + <style> blocks)
# ---------------------------------------------------------------------------

def check_color_contrast(soup):
    """
    Check colour contrast ratio for text elements.
    Covers:
      1. Inline style="color:...; background-color:..."
      2. Colors defined in <style> blocks matched by class/element selector
    Flags pairs with ratio < 4.5:1 (WCAG AA normal text).
    """
    issues = []
    MIN_RATIO = 4.5

    # --- Parse embedded stylesheets ---
    css_rules = {}
    for style_tag in soup.find_all('style'):
        css_rules.update(_parse_stylesheet_rules(style_tag.get_text()))

    def _get_css_colors(element):
        """Look up color/bg from CSS rules matching element's classes/tag."""
        txt, bg = None, None
        tag = element.name
        classes = element.get('class', [])

        # Check tag selector
        if tag in css_rules:
            rule = css_rules[tag]
            txt = txt or rule.get('color')
            bg = bg or rule.get('bg')

        # Check class selectors (most specific wins last)
        for cls in classes:
            key = '.' + cls
            if key in css_rules:
                rule = css_rules[key]
                txt = txt or rule.get('color')
                bg = bg or rule.get('bg')

        return txt, bg

    seen_pairs = set()
    text_elements = soup.find_all(['p', 'span', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                    'li', 'td', 'th', 'label', 'button', 'div'])

    for el in text_elements[:200]:  # cap to avoid huge pages
        # 1. Inline styles
        inline = el.get('style', '')
        txt_val, bg_val = _extract_inline_colors(inline)

        # 2. Fall back to CSS rules
        if not txt_val or not bg_val:
            css_txt, css_bg = _get_css_colors(el)
            txt_val = txt_val or css_txt
            bg_val = bg_val or css_bg

        if not txt_val or not bg_val:
            continue

        pair_key = (txt_val.lower(), bg_val.lower())
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        rgb_txt = _parse_color(txt_val)
        rgb_bg = _parse_color(bg_val)
        if not rgb_txt or not rgb_bg:
            continue

        ratio = _contrast_ratio(rgb_txt, rgb_bg)
        if ratio < MIN_RATIO:
            issues.append({
                'wcag_id': '1.4.3',
                'severity': 'serious',
                'message': (
                    f'Insufficient colour contrast ratio {ratio:.2f}:1 '
                    f'(text: {txt_val}, background: {bg_val}). '
                    f'Minimum required: {MIN_RATIO}:1.'
                ),
                'fix': (
                    'Increase the contrast between text and background colours. '
                    'Use a contrast checker tool to find compliant colour pairs.'
                ),
                'element': str(el)[:150]
            })

    return issues


# ---------------------------------------------------------------------------
# Keyboard navigation — WCAG 2.1.1 / 2.1.2
# ---------------------------------------------------------------------------

def check_keyboard_accessibility(soup):
    """
    WCAG 2.1.1 — All functionality must be operable via keyboard.
    Checks:
    - Interactive elements (div/span) with click handlers but no keyboard equivalent
    - tabindex="-1" on focusable elements that removes them from tab order
    - onclick on non-interactive elements without role or tabindex
    """
    issues = []
    interactive_tags = {'a', 'button', 'input', 'select', 'textarea'}

    # Check for non-interactive elements with onclick but no keyboard support
    for el in soup.find_all(attrs={'onclick': True}):
        tag = el.name
        if tag in interactive_tags:
            continue  # native interactive elements are fine
        has_tabindex = el.has_attr('tabindex') and el['tabindex'] != '-1'
        has_role = el.has_attr('role') and el['role'] in (
            'button', 'link', 'menuitem', 'tab', 'checkbox', 'radio', 'switch'
        )
        if not has_tabindex and not has_role:
            issues.append({
                'wcag_id': '2.1.1',
                'severity': 'serious',
                'message': (
                    f'<{tag}> element has onclick handler but is not keyboard accessible. '
                    'It has no tabindex or ARIA role to make it focusable.'
                ),
                'fix': (
                    'Add tabindex="0" and a keyboard event handler (onkeydown/onkeyup), '
                    'or replace with a <button> element.'
                ),
                'element': str(el)[:150]
            })

    # Check for positive tabindex values (disrupts natural tab order)
    for el in soup.find_all(attrs={'tabindex': True}):
        try:
            val = int(el['tabindex'])
            if val > 0:
                issues.append({
                    'wcag_id': '2.4.3',
                    'severity': 'moderate',
                    'message': (
                        f'Element has tabindex="{val}" which disrupts the natural tab order. '
                        'Positive tabindex values create confusing keyboard navigation.'
                    ),
                    'fix': 'Use tabindex="0" to include in natural order, or tabindex="-1" to exclude.',
                    'element': str(el)[:150]
                })
        except ValueError:
            pass

    return issues


def check_focus_indicators(soup):
    """
    WCAG 2.4.7 — Focus must be visible.
    Detects outline:none or outline:0 in inline styles which removes focus rings.
    """
    issues = []
    for el in soup.find_all(style=True):
        style = el.get('style', '').lower()
        if re.search(r'outline\s*:\s*(none|0)', style):
            tag = el.name
            if tag in ('a', 'button', 'input', 'select', 'textarea') or el.has_attr('tabindex'):
                issues.append({
                    'wcag_id': '2.4.7',
                    'severity': 'serious',
                    'message': (
                        f'<{tag}> element has outline removed via inline style, '
                        'making keyboard focus invisible.'
                    ),
                    'fix': (
                        'Remove "outline: none" from interactive elements. '
                        'Provide a custom :focus style instead of removing it entirely.'
                    ),
                    'element': str(el)[:150]
                })

    # Also check <style> blocks for outline:none on interactive selectors
    for style_tag in soup.find_all('style'):
        css = style_tag.get_text()
        # Look for patterns like a:focus { outline: none }
        matches = re.findall(
            r'([^{]*:focus[^{]*)\{[^}]*outline\s*:\s*(none|0)[^}]*\}',
            css, re.IGNORECASE
        )
        for selector, _ in matches:
            issues.append({
                'wcag_id': '2.4.7',
                'severity': 'serious',
                'message': (
                    f'CSS rule "{selector.strip()}" removes focus outline, '
                    'making keyboard focus invisible for that element.'
                ),
                'fix': 'Replace "outline: none" with a visible custom focus style.',
                'element': f'<style> ... {selector.strip()}:focus {{ outline: none }} ...'
            })

    return issues


def check_skip_navigation(soup):
    """
    WCAG 2.4.1 — A skip navigation link should be present on pages with repeated nav.
    Checks for a "skip to main content" link as the first focusable element.
    """
    issues = []
    # Only flag if there's a nav element (repeated navigation present)
    if not soup.find('nav'):
        return issues

    first_links = soup.find_all('a', limit=5)
    has_skip = False
    for link in first_links:
        text = link.get_text(strip=True).lower()
        href = link.get('href', '')
        if ('skip' in text or 'jump' in text) and href.startswith('#'):
            has_skip = True
            break

    if not has_skip:
        issues.append({
            'wcag_id': '2.4.1',
            'severity': 'moderate',
            'message': (
                'Page has navigation but no "skip to main content" link. '
                'Keyboard users must tab through all nav links on every page.'
            ),
            'fix': (
                'Add a skip link as the first element: '
                '<a href="#main-content" class="skip-link">Skip to main content</a>'
            ),
            'element': '<body> (first focusable element)'
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
    all_issues.extend(check_color_contrast(soup))
    all_issues.extend(check_keyboard_accessibility(soup))
    all_issues.extend(check_focus_indicators(soup))
    all_issues.extend(check_skip_navigation(soup))

    return all_issues
