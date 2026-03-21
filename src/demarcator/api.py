from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from demarcator.bootstrap import create_seeded_service
from demarcator.models import ApprovalDecision, RunRequest
from demarcator.services import DemarcatorError, NotFoundError, PermissionDeniedError


class DemarcatorRequestHandler(BaseHTTPRequestHandler):
    service = create_seeded_service()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        routes = {
            "/health": lambda: self._write_json(HTTPStatus.OK, {"status": "ok"}),
            "/summary": lambda: self._write_json(HTTPStatus.OK, self.service.summary()),
            "/connectors": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_connectors()}),
            "/workflows": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_workflows()}),
            "/rules": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_rules()}),
            "/people": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_people()}),
            "/activity": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_activity()}),
            "/approvals": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_approvals()}),
            "/audit": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_audit_events()}),
            "/alerts": lambda: self._write_json(HTTPStatus.OK, {"items": self.service.list_alerts()}),
        }
        handler = routes.get(parsed.path)
        if not handler:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": f"Route {parsed.path} was not found."})
            return
        handler()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json_body()
        if payload is None:
            return

        try:
            if parsed.path == "/runs":
                request = RunRequest.from_dict(payload)
                run = self.service.run_workflow(request)
                self._write_json(HTTPStatus.CREATED, run.to_dict())
                return

            if parsed.path.startswith("/approvals/") and parsed.path.endswith("/decision"):
                approval_id = parsed.path.split("/")[2]
                decision = ApprovalDecision(payload["decision"])
                result = self.service.decide_approval(
                    approval_id=approval_id,
                    reviewer_id=payload["reviewer_id"],
                    decision=decision,
                    note=payload.get("note"),
                )
                self._write_json(HTTPStatus.OK, result.to_dict())
                return
        except NotFoundError as exc:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        except PermissionDeniedError as exc:
            self._write_json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
            return
        except (DemarcatorError, KeyError, ValueError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": f"Route {parsed.path} was not found."})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length header."})
            return None
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})
            return None

    def _write_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    handler_class = type(
        "ConfiguredDemarcatorRequestHandler",
        (DemarcatorRequestHandler,),
        {"service": create_seeded_service()},
    )
    return ThreadingHTTPServer((host, port), handler_class)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Demarcator API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = build_server(args.host, args.port)
    print(f"Demarcator API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
