"""
LLM integration layer for WCAG Auditor — Phase 4.

Provider: Groq API (LLaMA 3.1 8B Instant)
- Fast (~1s per request)
- Free tier: 14,400 requests/day
- No local installation required
- API key configured in settings.py → GROQ_API_KEY
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PROMPT_ENHANCED_FIX = """You are a WCAG accessibility expert.

Issue found: {wcag_id} — {rule_title}
Message: {message}
Basic fix: {basic_fix}
Element: {element_snippet}

Give a concise developer fix (under 100 words):
1. Why it matters for disabled users (1 sentence)
2. Code fix example
"""

PROMPT_SEMANTIC_ANALYSIS = """Analyze this HTML for accessibility issues automated tools miss:

{html_snippet}

Check: ARIA roles, landmark regions, keyboard navigation, reading order.
Only list real issues found.
Format: ISSUE|wcag_id|severity|description|fix
If none: NO_ISSUES
"""

PROMPT_READABILITY = """Rate readability for cognitive accessibility (WCAG 3.1.5):

Title: {page_title}
Text: {text_sample}

Format (under 50 words):
LEVEL: <Simple|Moderate|Complex>
CONCERN: <concern or NONE>
IMPROVEMENT: <suggestion or NONE>
"""


# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------

class GroqClient:
    """Groq API client — LLaMA 3.1 8B Instant."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str) -> str | None:
        import time
        for attempt in range(3):
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a WCAG accessibility expert. Be very concise.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200,
                }
                resp = requests.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    # Try to extract retry-after from response headers
                    wait = (attempt + 1) * 5  # 5s, 10s
                    try:
                        import re
                        match = re.search(r'try again in (\d+\.?\d*)s', str(e), re.I)
                        if match:
                            wait = float(match.group(1)) + 1
                    except Exception:
                        pass
                    logger.warning(f"Groq rate limit hit, retrying in {wait:.0f}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"Groq request failed: {e}")
                    return None
        return None


# ---------------------------------------------------------------------------
# Unified LLM interface
# ---------------------------------------------------------------------------

class LLMClient:
    """Groq-backed LLM client for WCAG accessibility analysis."""

    def __init__(self):
        self._groq: GroqClient | None = None
        self._active_provider: str = "none"
        self._initialize()

    def _initialize(self):
        api_key = getattr(settings, "GROQ_API_KEY", "")
        model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")

        if api_key:
            self._groq = GroqClient(api_key, model)
            self._active_provider = "groq"
            logger.info(f"LLM: Using Groq ({model})")
        else:
            logger.warning(
                "LLM: GROQ_API_KEY not set. "
                "Add it to settings.py to enable AI analysis."
            )

    @property
    def provider(self) -> str:
        return self._active_provider

    @property
    def available(self) -> bool:
        return self._active_provider != "none"

    def complete(self, prompt: str) -> str | None:
        """Send a prompt and return the response, or None on failure."""
        if self._groq:
            return self._groq.complete(prompt)
        return None


# ---------------------------------------------------------------------------
# High-level analysis helpers
# ---------------------------------------------------------------------------

def get_llm_client() -> LLMClient:
    """Return a configured LLMClient instance."""
    return LLMClient()


def enhance_issue_fix(client: LLMClient, wcag_id: str, rule_title: str,
                      message: str, basic_fix: str, element_snippet: str = "") -> str | None:
    """
    Generate an enhanced, human-readable fix suggestion for a single issue.
    Returns the LLM response string, or None if unavailable.
    """
    if not client.available:
        return None
    prompt = PROMPT_ENHANCED_FIX.format(
        wcag_id=wcag_id,
        rule_title=rule_title,
        message=message,
        basic_fix=basic_fix,
        element_snippet=element_snippet[:200] if element_snippet else "N/A",
    )
    return client.complete(prompt)


def run_semantic_checks(client: LLMClient, html_snippet: str) -> list[dict]:
    """
    Run LLM-based semantic accessibility checks on an HTML snippet.
    Returns a list of issue dicts compatible with run_all_checks() output.
    """
    if not client.available or not html_snippet:
        return []

    prompt = PROMPT_SEMANTIC_ANALYSIS.format(html_snippet=html_snippet[:3000])
    response = client.complete(prompt)

    if not response or response.strip() == "NO_ISSUES":
        return []

    issues = []
    for line in response.splitlines():
        line = line.strip()
        if not line.startswith("ISSUE|"):
            continue
        parts = line.split("|")
        if len(parts) < 5:
            continue
        _, wcag_id, severity, description, fix = parts[:5]
        severity = severity.strip().lower()
        if severity not in ("critical", "serious", "moderate", "minor"):
            severity = "moderate"
        issues.append({
            "wcag_id": wcag_id.strip(),
            "severity": severity,
            "message": f"[AI] {description.strip()}",
            "fix": fix.strip(),
            "element": "",
            "source": "llm",
        })
    return issues


def analyze_readability(client: LLMClient, page_title: str, text_sample: str) -> dict | None:
    """
    Assess page readability for cognitive accessibility (WCAG 3.1.5).
    Returns a dict with keys: level, concern, improvement — or None.
    """
    if not client.available or not text_sample.strip():
        return None

    prompt = PROMPT_READABILITY.format(
        page_title=page_title or "Unknown",
        text_sample=text_sample[:200],
    )
    response = client.complete(prompt)
    if not response:
        return None

    result = {"level": "Unknown", "concern": None, "improvement": None}
    for line in response.splitlines():
        line = line.strip()
        if line.startswith("LEVEL:"):
            result["level"] = line.replace("LEVEL:", "").strip()
        elif line.startswith("CONCERN:"):
            val = line.replace("CONCERN:", "").strip()
            result["concern"] = None if val.upper() == "NONE" else val
        elif line.startswith("IMPROVEMENT:"):
            val = line.replace("IMPROVEMENT:", "").strip()
            result["improvement"] = None if val.upper() == "NONE" else val

    # Fallback if structured parsing missed the level
    if result["level"] == "Unknown":
        lower = response.lower()
        if "simple" in lower:
            result["level"] = "Simple"
        elif "complex" in lower:
            result["level"] = "Complex"
        elif "moderate" in lower:
            result["level"] = "Moderate"

    return result
