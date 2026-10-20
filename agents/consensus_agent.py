"""Consensus agent: merges every agent's output into one clean summary for the user.

The cross-referencing happens inside the model prompt; the reply contains only the findings.
Empty values are pruned before the model sees them and scrubbed from the reply.
"""
import json
import re

from agents.ollama_client import OllamaClient
from configs.config import Config

EMPTY_TEXT = {"", "n/a", "na", "none", "null", "nan", "unknown", "-", "--"}

# Sentences matching these talk about missing data or about the review process itself.
SCRUB_PATTERN = re.compile(
    r"\b(null|n/a|nan|not available|unavailable|not provided|not supplied|no data|"
    r"missing|not reported|could not be (?:retrieved|verified|found)|"
    r"cross[- ]?referenc\w*|consensus agent|the agents?|evidence (?:shows|suggests|availability)|"
    r"data sources?|retrieved evidence|provided evidence|supplied evidence)\b",
    re.IGNORECASE,
)

MAX_SOURCE_CHARS = 14000


def prune(value):
    """Recursively drop None, blank, 'N/A'-style values and empty containers."""
    if isinstance(value, dict):
        cleaned = {k: prune(v) for k, v in value.items()}
        return {k: v for k, v in cleaned.items() if not _is_empty(v)}
    if isinstance(value, (list, tuple)):
        cleaned = [prune(v) for v in value]
        return [v for v in cleaned if not _is_empty(v)]
    return value


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in EMPTY_TEXT
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    if isinstance(value, float) and value != value:
        return True
    return False


def scrub(text):
    """Remove sentences/bullets that mention missing values or the review process."""
    kept = []
    for line in str(text or "").splitlines():
        if not line.strip():
            kept.append("")
            continue
        prefix = re.match(r"\s*(?:[-*•]\s+|\d+[.)]\s+)?", line).group(0)
        body = line[len(prefix):]
        sentences = re.split(r"(?<=[.!?])\s+", body)
        good = [s for s in sentences if not SCRUB_PATTERN.search(s)]
        if good:
            kept.append(prefix + " ".join(good))
    out = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


class ConsensusAgent:

    def __init__(self):
        self.ollama = OllamaClient()

    def synthesize(self, message, sources, instructions=""):
        """Return a clean summary string, or '' if nothing usable was produced."""
        bundle = prune(sources if isinstance(sources, dict) else {})
        if not bundle:
            return ""
        evidence = json.dumps(bundle, indent=1, default=str)
        if len(evidence) > MAX_SOURCE_CHARS:
            evidence = self._shrink(bundle)

        prompt = f"""You are the lead analyst. Several specialist agents (market data, SEC filings, quant models, risk, research, sentiment, Robinhood and web evidence) each produced findings below. Use ALL of them: reconcile them, favor points that several independently support, and weigh conflicts by the reliability of each source.

USER REQUEST:
{message}

FINDINGS:
{evidence}

{instructions}

WRITE THE REPLY:
- Give only the conclusions: a direct, plain-language summary of what the combined findings say about the request, with the key numbers that matter.
- Use short paragraphs or a few bullets. Be decisive and concise (about 120-220 words).
- Do not describe your process. Never mention cross-referencing, agents, sources, data availability, or what is missing, null, unavailable or unknown. If a point has no supporting data, leave it out silently.
- Do not invent figures. Use only values present in the findings.
- Do not repeat tables; they are shown separately.
"""
        try:
            response = self.ollama.generate(
                prompt,
                model=getattr(Config, "CONSENSUS_MODEL", Config.HERMES_MODEL),
            )
        except Exception as exc:
            print("CONSENSUS AGENT FAILED:", repr(exc))
            return ""
        text = response.get("response", "") if isinstance(response, dict) else ""
        if not isinstance(text, str):
            return ""
        text = scrub(text)
        return text if len(text) >= 40 else ""

    @staticmethod
    def _shrink(bundle):
        """Trim each source evenly so every one stays represented."""
        budget = MAX_SOURCE_CHARS // max(1, len(bundle))
        parts = {}
        for key, value in bundle.items():
            raw = json.dumps(value, default=str)
            parts[key] = raw if len(raw) <= budget else raw[:budget] + "..."
        return json.dumps(parts, indent=1)
