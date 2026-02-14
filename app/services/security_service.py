from datetime import datetime, timezone

from app.database import pb


def log_event(
    event_type: str,
    severity: str,
    description: str,
    ip: str = "",
    user_id: str = "",
) -> None:
    try:
        data: dict = {
            "type": event_type,
            "severity": severity,
            "description": description,
            "ip": ip,
        }
        if user_id:
            data["userId"] = user_id
        pb.collection("security_events").create(data)
    except Exception:
        pass


def get_events(page: int = 1, per_page: int = 50) -> list[dict]:
    try:
        results = pb.collection("security_events").get_list(page, per_page, {"sort": "-created"})
        return [
            {
                "id": r.id,
                "type": getattr(r, "type", ""),
                "severity": getattr(r, "severity", ""),
                "description": getattr(r, "description", ""),
                "ip": getattr(r, "ip", ""),
                "timestamp": str(r.created),
            }
            for r in results.items
        ]
    except Exception:
        return []
