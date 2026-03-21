from __future__ import annotations

import argparse
import json
from urllib import error, request


def parse_source(value: str) -> dict[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("Sources must use connector_id:scope format.")
    connector_id, scope = value.split(":", 1)
    connector_id = connector_id.strip()
    scope = scope.strip()
    if not connector_id or not scope:
        raise argparse.ArgumentTypeError("Source connector and scope must both be non-empty.")
    return {"connector_id": connector_id, "scope": scope}


def build_payload(args: argparse.Namespace) -> dict:
    payload = {
        "actor_id": args.actor,
        "workflow_id": args.workflow,
        "requested_sources": args.source or [],
    }
    if args.correlation_id:
        payload["correlation_id"] = args.correlation_id
    if args.action_type or args.action_summary:
        if not args.action_type or not args.action_summary:
            raise SystemExit("--action-type and --action-summary must be provided together.")
        payload["requested_action"] = {
            "type": args.action_type,
            "summary": args.action_summary,
        }
    return payload


def submit_run(server: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        f"{server.rstrip('/')}/runs",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8")
        raise SystemExit(f"Demarcator API error {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Could not reach Demarcator API: {exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a workflow run from pi into Demarcator.")
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--source", action="append", type=parse_source, default=[])
    parser.add_argument("--correlation-id")
    parser.add_argument("--action-type")
    parser.add_argument("--action-summary")
    args = parser.parse_args()

    payload = build_payload(args)
    response = submit_run(args.server, payload)
    print(json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
