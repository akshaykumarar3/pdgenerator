import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from ..utils import date_utils


PAYER_KEYS = (
    "payer_id",
    "payer_name",
    "plan_name",
    "plan_type",
    "provider_abbreviation",
    "provider_policy_url",
    "plan_id",
    "plan_policy_url",
    "member_id",
    "policy_number",
)


LAB_ANALYTES = {
    "creatinine": {"aliases": ["creatinine", "cr", "scr"]},
    "egfr": {"aliases": ["egfr", "e-gfr", "e gfr"]},
    "bun": {"aliases": ["bun", "urea nitrogen"]},
    "co2": {"aliases": ["co2", "bicarb", "bicarbonate", "hco3"]},
    "potassium": {"aliases": ["potassium", "k"]},
    "hgb": {"aliases": ["hgb", "hemoglobin", "hb"]},
}


_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})\b")


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _get_attr(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _as_dict(content: Any) -> Optional[dict]:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        s = content.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _iter_strings(obj: Any):
    """
    Yield all (path, string) occurrences within nested dict/list content.
    """
    stack: list[tuple[str, Any]] = [("", obj)]
    while stack:
        path, cur = stack.pop()
        if isinstance(cur, str):
            yield path, cur
            continue
        if isinstance(cur, dict):
            for k, v in cur.items():
                k_str = str(k)
                stack.append((f"{path}.{k_str}" if path else k_str, v))
            continue
        if isinstance(cur, list):
            for i, v in enumerate(cur):
                stack.append((f"{path}[{i}]", v))


def _extract_date_hint(obj: Any) -> str:
    """
    Try common date keys or first date-like substring.
    """
    if isinstance(obj, dict):
        for k in ("service_date", "report_date", "study_date", "performed_date", "date"):
            v = obj.get(k)
            if v:
                return _safe_str(v)
    # scan strings
    for _path, s in _iter_strings(obj):
        m = _DATE_RE.search(s or "")
        if m:
            return m.group(1)
    return ""


def _normalize_payer_dict(raw: dict) -> dict:
    out = {}
    for k in PAYER_KEYS:
        v = raw.get(k)
        if v is None:
            continue
        s = _safe_str(v)
        if s:
            out[k] = s
    return out


def _payer_from_persona(patient_persona: Any) -> dict:
    payer = _get_attr(patient_persona, "payer")
    if not payer:
        return {}
    raw = {}
    for k in PAYER_KEYS:
        v = _get_attr(payer, k)
        if v is not None:
            raw[k] = v
    return _normalize_payer_dict(raw)


def _payer_from_patient_state(patient_state: Optional[dict]) -> dict:
    if not isinstance(patient_state, dict):
        return {}
    insurance = patient_state.get("insurance") or {}
    if not isinstance(insurance, dict):
        return {}
    return _normalize_payer_dict(insurance)


def _payer_from_document(doc_dict: dict) -> dict:
    if not isinstance(doc_dict, dict):
        return {}
    # Common PA-request shape
    payer_info = doc_dict.get("payer_information")
    if isinstance(payer_info, dict):
        return _normalize_payer_dict(payer_info)
    # Alternate/looser shapes: look for payer keys directly
    if any(k in doc_dict for k in ("payer_name", "plan_name", "member_id", "policy_number")):
        return _normalize_payer_dict(doc_dict)
    # Search nested dicts for payer_information-like blocks
    for _path, s in _iter_strings(doc_dict):
        _ = s  # only iterating strings for traversal; no-op
    # Walk nested dicts quickly
    stack = [doc_dict]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if any(k in cur for k in ("payer_name", "plan_name", "member_id", "policy_number")):
                cand = _normalize_payer_dict(cur)
                if cand.get("payer_name") and (cand.get("plan_name") or cand.get("plan_id")):
                    return cand
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return {}


def _policy_lens_from_payer(payer: dict) -> str:
    name = (payer.get("payer_name") or "").lower()
    plan_type = (payer.get("plan_type") or "").lower()
    plan_name = (payer.get("plan_name") or "").lower()
    if "medicare" in name or "medicare" in plan_type or "medicare" in plan_name:
        return "medicare"
    if "medicaid" in name or "medicaid" in plan_type or "medicaid" in plan_name:
        return "medicaid"
    if any(t in plan_type for t in ("ppo", "hmo", "commercial", "employer")):
        return "commercial"
    return "unknown"


def _parse_analytes(text: str) -> dict:
    """
    Parse analyte values from a blob of text. Returns map of canonical analyte -> value string.
    """
    if not text:
        return {}
    t = " " + text.strip() + " "
    out: dict[str, str] = {}

    def _find(alias: str) -> Optional[str]:
        # Capture values like: "Cr 8.7", "creatinine 8.7 mg/dL", "eGFR 5 mL/min/1.73m2"
        pattern = re.compile(
            rf"(?i)\b{re.escape(alias)}\b\s*[:=]?\s*([<>]?\s*\d+(?:\.\d+)?)\s*([a-zA-Z/%µ\.\-\d²\(\)]+)?"
        )
        m = pattern.search(t)
        if not m:
            return None
        num = _safe_str(m.group(1)).replace(" ", "")
        unit = _safe_str(m.group(2))
        return f"{num} {unit}".strip() if unit else num

    for canon, meta in LAB_ANALYTES.items():
        for alias in meta["aliases"]:
            val = _find(alias)
            if val:
                out[canon] = val
                break
    return out


def _panel_type_from_analytes(analytes: dict) -> str:
    if not analytes:
        return "lab"
    if "creatinine" in analytes or "egfr" in analytes:
        return "renal_labs"
    return "lab"


def _extract_panels_from_persona(patient_persona: Any) -> list[dict]:
    panels: list[dict] = []
    reports = _get_attr(patient_persona, "reports") or []
    for rep in reports:
        rep_date = _safe_str(_get_attr(rep, "date"))
        rep_results = _safe_str(_get_attr(rep, "results"))
        analytes = _parse_analytes(rep_results)
        if not analytes:
            continue
        d = date_utils.parse_date_any(rep_date)
        if not d:
            # allow panels without date, but they won't be used for recency ordering
            rep_date_norm = rep_date
        else:
            rep_date_norm = date_utils.format_mmddyyyy(d)
        panels.append(
            {
                "panel_type": _panel_type_from_analytes(analytes),
                "date": rep_date_norm,
                "analytes": analytes,
                "source_ref": "persona.reports",
            }
        )
    return panels


def _extract_panels_from_documents(documents: list) -> list[dict]:
    panels: list[dict] = []
    for doc in documents or []:
        content = _get_attr(doc, "content")
        doc_dict = _as_dict(content) if content is not None else None
        if not isinstance(doc_dict, dict):
            continue

        date_hint = _extract_date_hint(doc_dict)
        d = date_utils.parse_date_any(date_hint)
        date_norm = date_utils.format_mmddyyyy(d) if d else _safe_str(date_hint)

        # Parse analytes from all strings in the doc
        combined = []
        for _path, s in _iter_strings(doc_dict):
            if s and len(s) <= 2000:
                combined.append(s)
        analytes = _parse_analytes(" ".join(combined))
        if not analytes:
            continue

        panels.append(
            {
                "panel_type": _panel_type_from_analytes(analytes),
                "date": date_norm,
                "analytes": analytes,
                "source_ref": "documents",
            }
        )
    return panels


def _dedupe_panels(panels: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for p in panels:
        k = (str(p.get("panel_type") or ""), str(p.get("date") or ""))
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _panel_score(panel: dict) -> int:
    analytes = panel.get("analytes") or {}
    if not isinstance(analytes, dict):
        return 0
    return len([k for k in LAB_ANALYTES.keys() if k in analytes])


def _sort_key_by_date(panel: dict):
    d = date_utils.parse_date_any(panel.get("date") or "")
    return d or date.min


def _select_relevant_panels(panels: list[dict], max_items: int = 2) -> list[dict]:
    panels = [p for p in panels if isinstance(p, dict)]
    # Prefer dated panels; if none dated, keep top by score
    dated = [p for p in panels if date_utils.parse_date_any(p.get("date") or "")]
    if dated:
        dated.sort(key=lambda p: (_sort_key_by_date(p), _panel_score(p)), reverse=True)
        return dated[:max_items]
    panels.sort(key=lambda p: _panel_score(p), reverse=True)
    return panels[:max_items]


def build_objective_evidence_text(panels: list[dict]) -> str:
    panels = _select_relevant_panels(panels or [], max_items=2)
    if not panels:
        return ""

    def _fmt_panel(p: dict) -> str:
        d = _safe_str(p.get("date") or "")
        a = p.get("analytes") or {}
        parts = []
        for k in ("creatinine", "egfr", "bun", "co2", "potassium", "hgb"):
            if k in a and a.get(k):
                label = {"egfr": "eGFR", "bun": "BUN", "co2": "CO2", "hgb": "Hgb"}.get(k, k.title())
                parts.append(f"{label} {a[k]}")
        inner = ", ".join(parts)
        return f"{d}: {inner}".strip(": ").strip()

    # Most-recent first (already selected by recency)
    lines = [_fmt_panel(p) for p in panels if _fmt_panel(p)]
    if not lines:
        return ""

    text = "Objective evidence: " + " | ".join(lines) + "."
    return text.strip()


def build_canonical_facts(patient_state: Optional[dict], patient_persona: Any, documents: list) -> "CanonicalFacts":
    persona_payer = _payer_from_persona(patient_persona)
    doc_payer = {}
    for doc in documents or []:
        d = _as_dict(_get_attr(doc, "content"))
        if not d:
            continue
        cand = _payer_from_document(d)
        if cand:
            doc_payer = cand
            break
    state_payer = _payer_from_patient_state(patient_state)

    canonical_payer = persona_payer or doc_payer or state_payer
    lens = _policy_lens_from_payer(canonical_payer or {})

    panels = []
    panels.extend(_extract_panels_from_persona(patient_persona))
    panels.extend(_extract_panels_from_documents(documents or []))
    panels = _dedupe_panels(panels)

    return CanonicalFacts(
        canonical_payer=canonical_payer or {},
        numeric_evidence=panels,
        policy_lens=lens,
    )


def _has_payer_fields(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    return any(k in obj for k in ("payer_information", "payer_name", "plan_name", "member_id", "policy_number"))


def _looks_like_summary(doc_dict: dict) -> bool:
    if not isinstance(doc_dict, dict):
        return False
    summary_keys = {
        "case_profile_and_explanation",
        "expectation_after_extraction",
        "likelihood_after_extraction",
        "expectation_from_each_report",
        "overall_expectation_and_gaps",
    }
    if any(k in doc_dict for k in summary_keys):
        return True
    sections = doc_dict.get("sections")
    if isinstance(sections, list):
        sect = {str(s).strip() for s in sections}
        if sect & summary_keys:
            return True
    return False


def _looks_like_pa_request(doc_dict: dict) -> bool:
    if not isinstance(doc_dict, dict):
        return False
    if "clinical_justification" in doc_dict and ("payer_information" in doc_dict or _has_payer_fields(doc_dict)):
        return True
    # nested shapes (rare)
    if "requested_procedure" in doc_dict and "clinical_justification" in doc_dict:
        return True
    return False


def _inject_text(existing: Any, injection: str, marker: str = "Objective evidence:") -> Any:
    if not injection:
        return existing
    if isinstance(existing, str):
        if marker.lower() in existing.lower():
            return existing
        sep = "\n\n" if existing.strip() else ""
        return (existing.rstrip() + sep + injection).strip()
    # if it's a dict, store in a dedicated key
    if isinstance(existing, dict):
        v = existing.get("objective_evidence")
        if isinstance(v, str) and marker.lower() in v.lower():
            return existing
        existing = dict(existing)
        existing["objective_evidence"] = injection
        return existing
    return existing


def _fill_payer_in_doc(doc_dict: dict, canonical_payer: dict) -> dict:
    if not canonical_payer or not isinstance(doc_dict, dict):
        return doc_dict
    out = dict(doc_dict)

    if isinstance(out.get("payer_information"), dict):
        pi = dict(out["payer_information"])
        for k in PAYER_KEYS:
            if k in canonical_payer and (not _safe_str(pi.get(k)) or _safe_str(pi.get(k)).lower() in {"not provided", "n/a", "unknown"}):
                pi[k] = canonical_payer[k]
        out["payer_information"] = pi

    # loose top-level payer fields
    for k in ("payer_name", "plan_name", "plan_id", "member_id", "policy_number", "plan_type", "payer_id"):
        if k in canonical_payer and k in out:
            if not _safe_str(out.get(k)) or _safe_str(out.get(k)).lower() in {"not provided", "n/a", "unknown"}:
                out[k] = canonical_payer[k]

    return out


def apply_to_payload(payload: Any, patient_state: Optional[dict]) -> Any:
    """
    Mutates payload (documents + persona) to propagate canonical payer and objective evidence.
    Safe to call multiple times (idempotent).
    """
    if not payload or not getattr(payload, "patient_persona", None):
        return payload
    documents = getattr(payload, "documents", None) or []
    facts = build_canonical_facts(patient_state, payload.patient_persona, documents)
    payer = facts.canonical_payer or {}
    objective = build_objective_evidence_text(facts.numeric_evidence or [])

    # Persona payer: if missing fields, fill from canonical payer
    persona_payer = _get_attr(payload.patient_persona, "payer")
    if persona_payer and payer:
        for k in PAYER_KEYS:
            cur = _safe_str(_get_attr(persona_payer, k))
            if (not cur or cur.lower() in {"not provided", "n/a", "unknown"}) and payer.get(k):
                try:
                    setattr(persona_payer, k, payer[k])
                except Exception:
                    pass

    # Persona PA request clinical justification injection
    pa = _get_attr(payload.patient_persona, "pa_request")
    if pa and objective:
        try:
            existing = _safe_str(_get_attr(pa, "clinical_justification"))
            if "objective evidence:" not in existing.lower():
                setattr(pa, "clinical_justification", (existing + ("\n\n" if existing else "") + objective).strip())
        except Exception:
            pass

    # Documents enrichment
    for doc in documents:
        content = _get_attr(doc, "content")
        d = _as_dict(content)
        if not isinstance(d, dict):
            continue

        d2 = _fill_payer_in_doc(d, payer)
        if _looks_like_pa_request(d2) and objective:
            d2["clinical_justification"] = _inject_text(d2.get("clinical_justification", ""), objective)
        if _looks_like_summary(d2) and objective:
            # Prefer to inject into the primary narrative section if present, else store as key
            preferred_keys = [
                "case_profile_and_explanation",
                "expectation_after_extraction",
                "overall_expectation_and_gaps",
            ]
            injected = False
            for k in preferred_keys:
                if k in d2:
                    d2[k] = _inject_text(d2.get(k), objective)
                    injected = True
                    break
            if not injected:
                d2["objective_evidence"] = objective

        doc.content = d2

    return payload


def _contains_cannot_assess(items: list[str]) -> bool:
    if not items:
        return False
    pat = re.compile(
        r"(?i)\b(cannot|unable)\s+(?:to\s+)?assess\b|\binsufficient\b|\bnot\s+enough\s+information\b"
    )
    return any(pat.search(str(x) or "") for x in items)

def _normalize_summary_item(v: Any) -> str | None:
    s = _safe_str(v)
    if not s:
        return None
    # Remove common bullet prefixes and normalize whitespace
    s = re.sub(r"^\s*(?:[•\-\*\u2022]|\u26a0)\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _dedupe_keep_order(items: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items or []:
        s = _normalize_summary_item(raw)
        if not s:
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _why_for_attachment(title_hint: str) -> str:
    t = (title_hint or "").casefold()
    if any(k in t for k in ["mri", "ct", "xray", "x-ray", "ultrasound", "pet", "imaging"]):
        return "Provides objective imaging evidence supporting indication and severity."
    if any(k in t for k in ["lab", "cbc", "cmp", "metabolic", "a1c", "crp", "esr", "panel"]):
        return "Provides objective lab evidence supporting severity and risk stratification."
    if any(k in t for k in ["consult", "specialist", "cardiology", "orthopedic", "neuro", "oncology", "rheum"]):
        return "Documents specialist assessment, indication, and clinical rationale."
    if any(k in t for k in ["pt", "therapy", "physical", "conservative", "home exercise"]):
        return "Documents conservative treatment course and response/failed therapy."
    if any(k in t for k in ["note", "encounter", "progress", "visit", "h&p", "history", "exam"]):
        return "Documents symptoms, exam findings, and clinical course over time."
    if any(k in t for k in ["op note", "operative", "procedure", "surgery", "anesthesia"]):
        return "Documents procedural details and peri-procedural context."
    return "Supports medical necessity with objective clinical documentation."


def _extract_title_hint(doc: Any) -> str | None:
    hint = _get_attr(doc, "title_hint")
    s = _safe_str(hint)
    return s or None


def _collect_verification_items(summary_obj: Any, attr: str, field: str) -> list[Any]:
    param = getattr(summary_obj, attr, None)
    items = getattr(param, field, None) if param else None
    if not isinstance(items, list):
        return []
    return [x for x in items if x is not None]


def patch_concise_summary(
    summary_obj: Any,
    facts: "CanonicalFacts",
    documents: Optional[list[Any]] = None,
) -> Any:
    """
    Deterministically patch ConciseSummary output for payer + assessability.
    """
    if not summary_obj or not facts:
        return summary_obj
    payer = facts.canonical_payer or {}
    objective = build_objective_evidence_text(facts.numeric_evidence or [])

    # Ensure payer appears in details_from_extraction
    details = getattr(summary_obj, "details_from_extraction", None)
    if isinstance(details, list) and payer:
        payer_lines = []
        if payer.get("payer_name"):
            payer_lines.append(f"Payer: {payer['payer_name']}")
        if payer.get("plan_name"):
            payer_lines.append(f"Plan: {payer['plan_name']}")
        if payer.get("plan_id"):
            payer_lines.append(f"Plan ID: {payer['plan_id']}")
        if payer.get("member_id"):
            payer_lines.append(f"Member ID: {payer['member_id']}")
        if payer.get("policy_number"):
            payer_lines.append(f"Policy #: {payer['policy_number']}")
        existing_lower = " ".join([str(x).lower() for x in details if x is not None])
        for line in payer_lines:
            if line.lower() not in existing_lower:
                details.append(line)
        setattr(summary_obj, "details_from_extraction", details)

    # Policy compliance: avoid "cannot assess" when payer exists
    pc = getattr(summary_obj, "policy_compliance", None)
    if pc and payer:
        gaps = getattr(pc, "gaps_and_issues", None)
        correct = getattr(pc, "correct_items", None)
        if isinstance(gaps, list) and _contains_cannot_assess(gaps):
            # Replace generic inability statements with payer-aware checklist
            lens = facts.policy_lens or "unknown"
            checklist = []
            checklist.append(f"Policy lens: {lens} (derived from payer/plan).")
            if objective:
                checklist.append(objective)
            checklist.append("Assessment is based on available documentation; missing criteria are listed below if any.")
            new_correct = list(correct) if isinstance(correct, list) else []
            for item in checklist:
                if item and item not in new_correct:
                    new_correct.append(item)
            setattr(pc, "correct_items", new_correct)
            # Remove generic gaps and keep only concrete missing items (best-effort)
            new_gaps = [
                g
                for g in gaps
                if not re.search(r"(?i)\b(cannot|unable)\s+(?:to\s+)?assess\b|\binsufficient\b", str(g or ""))
            ]
            setattr(pc, "gaps_and_issues", new_gaps)

    # Attachments list: if missing, derive from generated documents (title_hint + 1-line why)
    try:
        attachments = getattr(summary_obj, "attachments_list", None)
        attachments_list = attachments if isinstance(attachments, list) else []
        docs = documents or []
        if (not attachments_list) and docs:
            derived: list[str] = []
            for d in docs:
                hint = _extract_title_hint(d)
                if not hint:
                    continue
                pretty = hint.replace("_", " ").strip()
                derived.append(f"{pretty} — {_why_for_attachment(hint)}")
            attachments_list = _dedupe_keep_order(derived)
        else:
            attachments_list = _dedupe_keep_order(attachments_list)
        setattr(summary_obj, "attachments_list", attachments_list)
    except Exception:
        # Best-effort only; do not fail summary generation
        pass

    # Post-attachment likelihood expectations: aggregate from verification sections, cap 5 each
    try:
        order = [
            "medical_necessity",
            "policy_compliance",
            "clinical_timeline_strength",
            "documentation_quality",
        ]

        correct_agg: list[Any] = []
        gaps_agg: list[Any] = []
        for a in order:
            correct_agg.extend(_collect_verification_items(summary_obj, a, "correct_items"))
            gaps_agg.extend(_collect_verification_items(summary_obj, a, "gaps_and_issues"))

        correct_derived = _dedupe_keep_order(correct_agg)[:5]
        gaps_derived = _dedupe_keep_order(gaps_agg)[:5]

        existing = getattr(summary_obj, "likelihood_expectations_post_attachments", None)
        existing_correct = (
            _dedupe_keep_order(getattr(existing, "correct_items", None) or [])
            if existing
            else []
        )[:5]
        existing_gaps = (
            _dedupe_keep_order(getattr(existing, "gaps_and_issues", None) or [])
            if existing
            else []
        )[:5]

        final_correct = existing_correct or correct_derived
        final_gaps = existing_gaps or gaps_derived

        if final_correct or final_gaps:
            from . import models as ai_models

            setattr(
                summary_obj,
                "likelihood_expectations_post_attachments",
                ai_models.VerificationParameter(
                    correct_items=final_correct,
                    gaps_and_issues=final_gaps,
                ),
            )
        else:
            setattr(summary_obj, "likelihood_expectations_post_attachments", None)
    except Exception:
        # Best-effort only; do not fail summary generation
        pass

    return summary_obj


@dataclass
class CanonicalFacts:
    canonical_payer: dict
    numeric_evidence: list[dict]
    policy_lens: str
