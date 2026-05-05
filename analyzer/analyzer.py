import requests
from bs4 import BeautifulSoup
from core.models import Rule, Issue

level_map = {"A": ["A"], "AA": ["A", "AA"], "AAA": ["A", "AA", "AAA"]}

def run_analyzer(page):
    soup = BeautifulSoup(page.html_snapshot, "html.parser")
    issues_list = []
    allowed = level_map.get(page.project.wcag_level, ["A", "AA"])
    check_missing_alt(soup, page, issues_list, allowed)
    check_missing_labels(soup, page, issues_list, allowed)
    check_lang_attribute(soup, page, issues_list, allowed)
    check_page_title(soup, page, issues_list, allowed)
    check_heading_hierarchy(soup, page, issues_list, allowed)
    check_vague_links(soup, page, issues_list, allowed)
    check_empty_buttons(soup, page, issues_list, allowed)
    check_missing_input_labels(soup, page, issues_list, allowed)
    check_color_contrast(soup, page, issues_list, allowed)
    if len(issues_list) > 0:
        page.status = "fail"
    else:
        page.status = "pass"
    page.save()
    return issues_list

def get_rule(wcag_id, allowed):
    try:
        r = Rule.objects.get(wcag_id=wcag_id)
        if r.level in allowed:
            return r
        return None
    except:
        return None

def check_missing_alt(soup, page, issues_list, allowed):
    rule = get_rule("1.1.1", allowed)
    if rule is None:
        return
    all_imgs = soup.find_all("img")
    for img in all_imgs:
        alt_text = img.get("alt")
        if not alt_text:
            new_issue = Issue.objects.create(page=page, rule=rule, severity="critical", message="Image is missing alt text: " + str(img.get("src", "no src")), fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_missing_labels(soup, page, issues_list, allowed):
    rule = get_rule("1.3.1", allowed)
    if rule is None:
        return
    skip_types = ["hidden", "submit", "button", "reset"]
    all_inputs = soup.find_all("input")
    for inp in all_inputs:
        input_type = inp.get("type")
        if input_type in skip_types:
            continue
        inp_id = inp.get("id")
        found_label = False
        if inp_id:
            lbl = soup.find("label", {"for": inp_id})
            if lbl:
                found_label = True
        aria = inp.get("aria-label")
        aria2 = inp.get("aria-labelledby")
        if found_label == False and not aria and not aria2:
            new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="Input field has no label: " + str(inp.get("name", "unknown")), fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_lang_attribute(soup, page, issues_list, allowed):
    rule = get_rule("3.1.1", allowed)
    if rule is None:
        return
    html_tag = soup.find("html")
    if html_tag:
        lang = html_tag.get("lang")
        if not lang:
            new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="The html tag does not have a lang attribute", fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_page_title(soup, page, issues_list, allowed):
    rule = get_rule("2.4.2", allowed)
    if rule is None:
        return
    title_tag = soup.find("title")
    if not title_tag:
        new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="Page has no title tag at all", fix=rule.fix_suggestion)
        issues_list.append(new_issue)
    else:
        title_text = title_tag.get_text(strip=True)
        if title_text == "":
            new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="Page title tag is empty", fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_heading_hierarchy(soup, page, issues_list, allowed):
    rule = get_rule("2.4.6", allowed)
    if rule is None:
        return
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    heading_levels = []
    for h in headings:
        num = int(h.name[1])
        heading_levels.append(num)
    i = 1
    while i < len(heading_levels):
        diff = heading_levels[i] - heading_levels[i-1]
        if diff > 1:
            new_issue = Issue.objects.create(page=page, rule=rule, severity="moderate", message="Heading jumps from h" + str(heading_levels[i-1]) + " to h" + str(heading_levels[i]), fix=rule.fix_suggestion)
            issues_list.append(new_issue)
            break
        i = i + 1

def check_vague_links(soup, page, issues_list, allowed):
    rule = get_rule("2.4.4", allowed)
    if rule is None:
        return
    bad_link_texts = ["click here", "read more", "here", "more", "link", "this"]
    all_links = soup.find_all("a", href=True)
    for lnk in all_links:
        txt = lnk.get_text(strip=True).lower()
        if txt in bad_link_texts:
            new_issue = Issue.objects.create(page=page, rule=rule, severity="moderate", message="Link text is not descriptive: " + lnk.get_text(strip=True), fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_empty_buttons(soup, page, issues_list, allowed):
    rule = get_rule("4.1.2", allowed)
    if rule is None:
        return
    all_buttons = soup.find_all("button")
    for btn in all_buttons:
        btn_text = btn.get_text(strip=True)
        aria_lbl = btn.get("aria-label")
        aria_lbl2 = btn.get("aria-labelledby")
        if not btn_text and not aria_lbl and not aria_lbl2:
            new_issue = Issue.objects.create(page=page, rule=rule, severity="critical", message="Button has no text and no aria-label", fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_missing_input_labels(soup, page, issues_list, allowed):
    rule = get_rule("3.3.2", allowed)
    if rule is None:
        return
    textareas = soup.find_all("textarea")
    selects = soup.find_all("select")
    all_elements = textareas + selects
    for el in all_elements:
        el_id = el.get("id")
        has_lbl = False
        if el_id:
            lbl = soup.find("label", {"for": el_id})
            if lbl:
                has_lbl = True
        if has_lbl == False and not el.get("aria-label"):
            new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="Form element is missing a label: " + el.name, fix=rule.fix_suggestion)
            issues_list.append(new_issue)

def check_broken_links(soup, page, issues_list, allowed):
    rule = get_rule("4.1.1", allowed)
    if rule is None:
        return
    count = 0
    all_links = soup.find_all("a", href=True)
    for a in all_links:
        if count >= 10:
            break
        href = a["href"].strip()
        if not href:
            continue
        if href.startswith("#"):
            continue
        if href.startswith("mailto:"):
            continue
        if href.startswith("javascript:"):
            continue
        if not href.startswith("http"):
            continue
        count = count + 1
        try:
            res = requests.head(href, timeout=2, allow_redirects=True)
            if res.status_code >= 400:
                new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="Broken link found (" + str(res.status_code) + "): " + href, fix="Remove or fix this broken link")
                issues_list.append(new_issue)
        except Exception:
            pass

def hex_to_rgb(hex_color):
    hex_color = hex_color.replace("#", "")
    if len(hex_color) == 3:
        hex_color = hex_color[0] + hex_color[0] + hex_color[1] + hex_color[1] + hex_color[2] + hex_color[2]
    if len(hex_color) != 6:
        return None
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return r, g, b
    except:
        return None

def get_luminance(r, g, b):
    def calc(c):
        c = c / 255.0
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * calc(r) + 0.7152 * calc(g) + 0.0722 * calc(b)

def get_contrast(color1, color2):
    lum1 = get_luminance(color1[0], color1[1], color1[2])
    lum2 = get_luminance(color2[0], color2[1], color2[2])
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    ratio = (lighter + 0.05) / (darker + 0.05)
    return ratio

def check_color_contrast(soup, page, issues_list, allowed):
    rule = get_rule("1.4.3", allowed)
    if rule is None:
        return
    elements_with_style = soup.find_all(style=True)
    for el in elements_with_style:
        style_str = el.get("style", "")
        txt_color = None
        bg_color = None
        parts = style_str.split(";")
        for part in parts:
            part = part.strip()
            if part.startswith("color:"):
                txt_color = part.split(":")[1].strip()
            if part.startswith("background-color:") or part.startswith("background:"):
                bg_color = part.split(":")[1].strip()
        if txt_color and bg_color:
            if txt_color.startswith("#") and bg_color.startswith("#"):
                rgb1 = hex_to_rgb(txt_color)
                rgb2 = hex_to_rgb(bg_color)
                if rgb1 and rgb2:
                    ratio = get_contrast(rgb1, rgb2)
                    if ratio < 4.5:
                        new_issue = Issue.objects.create(page=page, rule=rule, severity="serious", message="Color contrast is too low " + str(round(ratio, 2)) + ":1 on " + el.name, fix=rule.fix_suggestion)
                        issues_list.append(new_issue)
