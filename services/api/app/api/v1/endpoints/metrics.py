from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse


router = APIRouter(prefix="/api/v1/metrics")


def _label_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


@router.get("", response_class=PlainTextResponse)
def metrics(request: Request) -> PlainTextResponse:
    settings = request.app.state.settings
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
