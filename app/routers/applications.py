from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import pb
from app.dependencies import get_current_user
from app.models.application import ApplicationCreateRequest

router = APIRouter()


def _app_to_response(record) -> dict:
    created = record.created
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "id": record.id,
        "userId": getattr(record, "user", ""),
        "userName": getattr(record, "user_name", ""),
        "projectName": getattr(record, "project_name", ""),
        "useCase": getattr(record, "use_case", ""),
        "requestedQuota": getattr(record, "requested_quota", 0) or 0,
        "status": getattr(record, "status", "pending"),
        "createdAt": str(created),
    }


@router.post("")
async def create_application(body: ApplicationCreateRequest, user: dict = Depends(get_current_user)):
    record = pb.collection("api_applications").create({
        "user": user["id"],
        "userName": user["name"],
        "projectName": body.projectName,
        "useCase": body.useCase,
        "requestedQuota": body.requestedQuota,
        "targetModel": body.targetModel or "",
        "status": "pending",
        "adminNote": "",
    })
    return _app_to_response(record)


@router.get("")
async def list_applications(user: dict = Depends(get_current_user)):
    results = pb.collection("api_applications").get_list(
        1, 50, {"filter": f'user="{user["id"]}"', "sort": "-created"}
    )
    return [_app_to_response(r) for r in results.items]
