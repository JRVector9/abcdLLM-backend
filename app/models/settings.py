from pydantic import BaseModel
from typing import Optional


class UserSettingsResponse(BaseModel):
    autoModelUpdate: bool = False
    detailedLogging: bool = False
    ipWhitelist: str = ""
    emailSecurityAlerts: bool = False
    usageThresholdAlert: bool = False


class UserSettingsUpdateRequest(BaseModel):
    autoModelUpdate: Optional[bool] = None
    detailedLogging: Optional[bool] = None
    emailSecurityAlerts: Optional[bool] = None
    usageThresholdAlert: Optional[bool] = None


class WhitelistUpdateRequest(BaseModel):
    ipWhitelist: str
