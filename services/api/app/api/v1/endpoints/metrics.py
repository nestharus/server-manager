from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import ApiContainer
from app.core.settings import Settings


router = APIRouter(prefix="/api/v1/metrics")


def _label_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


@router.get("", response_class=PlainTextResponse)
@inject
def metrics(
    settings: Settings = Depends(Provide[ApiContainer.core.settings]),
) -> PlainTextResponse:
    info_labels = (
        'service="server-manager-api",'
        f'version="{_label_value(settings.app_version)}",'
        f'channel="{_label_value(settings.platform_channel)}",'
        f'tenant="{_label_value(settings.platform_tenant)}"'
    )
    ready_labels = (
        f'channel="{_label_value(settings.platform_channel)}",'
        f'tenant="{_label_value(settings.platform_tenant)}"'
    )
    body = "\n".join(
        [
            "# HELP server_manager_api_info Static API build information.",
            "# TYPE server_manager_api_info gauge",
            "server_manager_api_info{" + info_labels + "} 1",
            "# HELP server_manager_api_ready Static scrape reachability signal.",
            "# TYPE server_manager_api_ready gauge",
            "server_manager_api_ready{" + ready_labels + "} 1",
            "",
        ]
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
