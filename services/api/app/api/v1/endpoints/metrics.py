from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse


router = APIRouter(prefix="/api/v1/metrics")


@router.get("", response_class=PlainTextResponse)
def metrics(request: Request) -> PlainTextResponse:
    settings = request.app.state.settings
    body = "\n".join(
        [
            "# HELP server_manager_api_info Static API build information.",
            "# TYPE server_manager_api_info gauge",
            (
                'server_manager_api_info{service="server-manager-api",'
                f'version="{settings.app_version}",channel="local",tenant="platform"}} 1'
            ),
            "# HELP server_manager_api_ready Static scrape reachability signal.",
            "# TYPE server_manager_api_ready gauge",
            'server_manager_api_ready{channel="local",tenant="platform"} 1',
            "",
        ]
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
