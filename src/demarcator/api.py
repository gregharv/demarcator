from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from demarcator.bootstrap import DEFAULT_DB_PATH, create_seeded_service
from demarcator.models import ApprovalDecision, RunRequest
from demarcator.services import DemarcatorError, NotFoundError, PermissionDeniedError


class DemarcatorAPI:
    def __init__(self, service):
        self.service = service

    def handle(self, method: str, path: str, body: bytes | None = None) -> tuple[HTTPStatus, dict]:
        parsed = urlparse(path)
        if method == "GET":
            return self._handle_get(parsed.path)
        if method == "POST":
            return self._handle_post(parsed.path, body or b"{}")
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"Method {method} is not supported."}

    def _handle_get(self, path: str) -> tuple[HTTPStatus, dict]:
        routes = {
            "/health": {"status": "ok"},
            "/summary": self.service.summary(),
            "/connectors": {"items": self.service.list_connectors()},
            "/workflows": {"items": self.service.list_workflows()},
            "/rules": {"items": self.service.list_rules()},
            "/people": {"items": self.service.list_people()},
            "/activity": {"items": self.service.list_activity()},
            "/approvals": {"items": self.service.list_approvals()},
            "/audit": {"items": self.service.list_audit_events()},
            "/alerts": {"items": self.service.list_alerts()},
        }
        payload = routes.get(path)
        if payload is None:
            return HTTPStatus.NOT_FOUND, {"error": f"Route {path} was not found."}
        return HTTPStatus.OK, payload

    def _handle_post(self, path: str, body: bytes) -> tuple[HTTPStatus, dict]:
        payload, error_status = self._read_json_body(body)
        if error_status:
            return error_status
        try:
            if path == "/runs":
                request = RunRequest.from_dict(payload)
                run = self.service.run_workflow(request)
                return HTTPStatus.CREATED, run.to_dict()

            if path.startswith("/approvals/") and path.endswith("/decision"):
                approval_id = path.split("/")[2]
                decision = ApprovalDecision(payload["decision"])
                result = self.service.decide_approval(
                    approval_id=approval_id,
                    reviewer_id=payload["reviewer_id"],
                    decision=decision,
                    note=payload.get("note"),
                )
                return HTTPStatus.OK, result.to_dict()
        except NotFoundError as exc:
            return HTTPStatus.NOT_FOUND, {"error": str(exc)}
        except PermissionDeniedError as exc:
            return HTTPStatus.FORBIDDEN, {"error": str(exc)}
        except (DemarcatorError, KeyError, ValueError) as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        return HTTPStatus.NOT_FOUND, {"error": f"Route {path} was not found."}

    def _read_json_body(self, body: bytes) -> tuple[dict, tuple[HTTPStatus, dict] | None]:
        raw_body = body or b"{}"
        try:
            return json.loads(raw_body.decode("utf-8")), None
        except json.JSONDecodeError:
            return {}, (HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})


class DemarcatorRequestHandler(BaseHTTPRequestHandler):
    app: DemarcatorAPI | None = None

    def do_GET(self) -> None:  # noqa: N802
        if self.app is None:
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "API app is not configured."})
            return
        status, payload = self.app.handle("GET", self.path)
        self._write_json(status, payload)

    def do_POST(self) -> None:  # noqa: N802
        if self.app is None:
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "API app is not configured."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length header."})
            return
        body = self.rfile.read(length) if length else b"{}"
        status, payload = self.app.handle("POST", self.path, body)
        self._write_json(status, payload)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_api(db_path: str = DEFAULT_DB_PATH) -> DemarcatorAPI:
    return DemarcatorAPI(create_seeded_service(db_path))


def build_server(host: str, port: int, db_path: str = DEFAULT_DB_PATH) -> ThreadingHTTPServer:
    handler_class = type(
        "ConfiguredDemarcatorRequestHandler",
        (DemarcatorRequestHandler,),
        {"app": build_api(db_path)},
    )
    return ThreadingHTTPServer((host, port), handler_class)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Demarcator API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    server = build_server(args.host, args.port, args.db_path)
    print(f"Demarcator API listening on http://{args.host}:{args.port} using {args.db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
