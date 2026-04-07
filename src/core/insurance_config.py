import json
import os
from typing import Any, Dict, List, Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(_BASE_DIR)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "core", "insurance_config.json")

_cached_config: Optional[Dict[str, Any]] = None


def _normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize provider/plan shapes to list-based structures."""
    normalized = dict(cfg or {})

    providers = normalized.get("providers")
    providers_list: List[Dict[str, Any]] = []
    if isinstance(providers, dict):
        for provider_id, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            p = dict(provider)
            p.setdefault("provider_id", provider_id)
            providers_list.append(p)
    elif isinstance(providers, list):
        providers_list = [p for p in providers if isinstance(p, dict)]

    # Normalize plans for each provider
    for provider in providers_list:
        plans = provider.get("plans")
        plans_list: List[Dict[str, Any]] = []
        if isinstance(plans, dict):
            for key, val in plans.items():
                if isinstance(val, list):
                    for item in val:
                        if not isinstance(item, dict):
                            continue
                        plan = dict(item)
                        if plan.get("plan_id") is None and isinstance(key, str):
                            plan["plan_id"] = key
                        if plan.get("plan_type") is None and isinstance(key, str):
                            plan["plan_type"] = key
                        plans_list.append(plan)
                elif isinstance(val, dict):
                    plan = dict(val)
                    if plan.get("plan_id") is None and isinstance(key, str):
                        plan["plan_id"] = key
                    plans_list.append(plan)
        elif isinstance(plans, list):
            plans_list = [p for p in plans if isinstance(p, dict)]

        provider["plans"] = plans_list

    normalized["providers"] = providers_list
    return normalized


def _load_config() -> Dict[str, Any]:
    if not os.path.exists(_CONFIG_PATH):
        return {"default_provider_id": None, "providers": []}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _normalize_config(raw)


def get_config(force_reload: bool = False) -> Dict[str, Any]:
    global _cached_config
    if _cached_config is None or force_reload:
        _cached_config = _load_config()
    return _cached_config or {"default_provider_id": None, "providers": []}


def get_default_provider_id() -> Optional[str]:
    return (get_config().get("default_provider_id") or None)


def get_providers() -> List[Dict[str, Any]]:
    return list(get_config().get("providers") or [])


def get_provider_by_id(provider_id: str) -> Optional[Dict[str, Any]]:
    if not provider_id:
        return None
    for p in get_providers():
        if p.get("provider_id") == provider_id:
            return p
    return None


def get_default_provider() -> Optional[Dict[str, Any]]:
    pid = get_default_provider_id()
    return get_provider_by_id(pid) if pid else None


def resolve_plan(
    provider: Optional[Dict[str, Any]],
    plan_type: Optional[str] = None,
    plan_id: Optional[str] = None,
    fallback_plan_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not provider:
        return None
    plans = provider.get("plans") or []
    if not plans:
        return None

    # 1) Exact plan_id match
    if plan_id:
        for p in plans:
            if p.get("plan_id") == plan_id:
                return p

    # 2) Match existing plan name if present and plan_type aligns
    if fallback_plan_name:
        for p in plans:
            if p.get("plan_name") == fallback_plan_name and (not plan_type or p.get("plan_type") == plan_type):
                return p

    # 3) Default plan by type
    if plan_type:
        for p in plans:
            if p.get("plan_type") == plan_type and p.get("is_default") is True:
                return p

    # 4) First plan with matching type
    if plan_type:
        for p in plans:
            if p.get("plan_type") == plan_type:
                return p

    # 5) Fallback to provider default, else first plan
    for p in plans:
        if p.get("is_default") is True:
            return p
    return plans[0]
