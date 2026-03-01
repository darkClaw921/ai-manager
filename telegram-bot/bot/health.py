"""Simple health check HTTP server for Docker healthchecks.

Runs on port 8080 alongside the main bot webhook server (8443).
Checks connectivity to the backend API.
"""

import asyncio
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import httpx

from bot.config import get_bot_settings

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler that responds to GET /health."""

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        settings = get_bot_settings()
        services = {}
        status = "ok"

        # Check backend API connectivity
        try:
            with httpx.Client(timeout=2) as client:
                resp = client.get(f"{settings.BACKEND_API_URL}/health")
                if resp.status_code == 200:
                    services["backend_api"] = "ok"
                else:
                    services["backend_api"] = "error"
                    status = "degraded"
        except Exception:
            services["backend_api"] = "error"
            status = "degraded"

        # Check bot token validity (simple test)
        try:
            with httpx.Client(timeout=2) as client:
                resp = client.get(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
                )
                if resp.status_code == 200:
                    services["telegram_api"] = "ok"
                else:
                    services["telegram_api"] = "error"
                    status = "degraded"
        except Exception:
            services["telegram_api"] = "error"
            status = "degraded"

        import json
        body = json.dumps({"status": status, "services": services}).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        """Suppress default request logging to avoid noise."""
        pass


def start_health_server(port: int = 8080) -> None:
    """Start the health check HTTP server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server started on port %d", port)
