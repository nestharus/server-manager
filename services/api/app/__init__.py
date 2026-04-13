"""Humility server-manager API service.

FastAPI application providing the mutation gateway for the Discord
server management platform. Both the web UI and the Discord daemon
route through this API.

Internal architecture follows the ai-workflow layered pattern:
api -> services -> repositories -> infrastructure.
"""
