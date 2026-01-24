from datetime import datetime
from enum import Enum
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, BaseSettings

def keyvault_name_as_attr(name: str) -> str:
    return name.replace("-", "_").upper()


class Settings(BaseSettings):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load secrets from keyvault
        if self.AZURE_KEY_VAULT_ENDPOINT:
            credential = DefaultAzureCredential()
            keyvault_client = SecretClient(self.AZURE_KEY_VAULT_ENDPOINT, credential)
            for secret in keyvault_client.list_properties_of_secrets():
                setattr(
                    self,
                    keyvault_name_as_attr(secret.name),
                    keyvault_client.get_secret(secret.name).value,
                )

    AZURE_COSMOS_CONNECTION_STRING: str = ""
    AZURE_COSMOS_DATABASE_NAME: str = "Todo"
    AZURE_KEY_VAULT_ENDPOINT: Optional[str] = None
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = None
    APPLICATIONINSIGHTS_ROLENAME: Optional[str] = "API"
    STRAVA_REDIRECT_URI: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class UserToken(Document):
    user_id: str
    access_token: str
    refresh_token: str
    expires_at: int
    created_at: datetime = datetime.utcnow()

    class Settings:
        name = "user_tokens"


class Activity(BaseModel):
    id: int
    name: str
    start_date: str
    type: str
    distance: float
    moving_time: int
    elapsed_time: int
    total_elevation_gain: float
    workout_type: Optional[int]
    average_speed: float
    max_speed: float
    has_heartrate: bool
    average_heartrate: Optional[float]
    max_heartrate: Optional[float]
    heartrate_opt_out: bool
    display_hide_heartrate_option: bool
    elev_high: Optional[float]
    elev_low: Optional[float]
    pr_count: int
    total_photo_count: int
    has_kudoed: bool


class MergeRequest(BaseModel):
    activity_ids: list[int]
    name: str = "Merged Activity"
    description: str = "Merged from multiple activities"


__beanie_models__ = [UserToken]
