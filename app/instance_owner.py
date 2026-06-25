from urllib.parse import urlparse

from app.database import supabase

_owner_id: str | None = None
_agent_url: str | None = None


def set_agent_url(url: str) -> None:
    global _agent_url
    _agent_url = url.rstrip("/")


def register_owner(user_id: str) -> None:
    global _owner_id
    _owner_id = user_id


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def _url_variants(url: str) -> list[str]:
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    variants = {normalized}
    if parsed.hostname == "localhost":
        variants.add(f"{parsed.scheme}://127.0.0.1:{parsed.port or 80}")
    elif parsed.hostname == "127.0.0.1":
        variants.add(f"{parsed.scheme}://localhost:{parsed.port or 80}")
    return list(variants)


def _lookup_owner_by_agent_url(agent_url: str) -> str | None:
    for variant in _url_variants(agent_url):
        result = (
            supabase.table("agent_profiles")
            .select("user_id")
            .eq("agent_url", variant)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["user_id"]
    return None


def resolve_instance_owner_id() -> str:
    if _owner_id:
        return _owner_id

    if _agent_url:
        looked_up = _lookup_owner_by_agent_url(_agent_url)
        if looked_up:
            register_owner(looked_up)
            return looked_up

    raise RuntimeError(
        "This agent instance has no registered owner. "
        "Open the app in a browser and sign in once so heartbeat can register it."
    )
