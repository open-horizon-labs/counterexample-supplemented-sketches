from __future__ import annotations

import os
from typing import Any

# Same defaults as Recon local-dev (appsettings.json + local-dev/.env.example).
DEFAULT_AWS_PROFILE = "review"
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_MODEL_ID = (
    "arn:aws:bedrock:us-east-1:609525944595:application-inference-profile/xomiuwisz5mh"
)

TOOL_NAME = "emit_roster_suggestions"


def aws_profile() -> str:
    return (
        os.environ.get("ROSTERSYNTH_AWS_PROFILE")
        or os.environ.get("AWS_PROFILE")
        or DEFAULT_AWS_PROFILE
    )


def default_model_id() -> str:
    return os.environ.get("ROSTERSYNTH_BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)


def default_region() -> str:
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_AWS_REGION
    )


def _bedrock_client():
    import boto3

    session = boto3.Session(profile_name=aws_profile(), region_name=default_region())
    return session.client("bedrock-runtime")


def _tool_schema() -> dict[str, Any]:
    adjustment = {
        "type": "object",
        "properties": {
            "shiftKind": {"type": "integer"},
            "hours": {"type": "number"},
            "workDate": {"type": "string"},
            "status": {"type": "integer"},
        },
        "required": ["shiftKind", "hours", "workDate"],
    }
    suggestion_item = {
        "type": "object",
        "properties": {
            "employeeId": {"type": "string"},
            "issueType": {
                "type": "string",
                "enum": ["coverage-hour-gap", "cancel-duplicate-booking"],
            },
            "op": {"type": "string", "enum": ["append", "modify"]},
            "suggestion": {"type": "string"},
            "adjustment": adjustment,
            "bookingId": {"type": "integer"},
            "fields": {
                "type": "object",
                "properties": {"status": {"type": "integer", "enum": [4]}},
                "required": ["status"],
            },
        },
        "required": ["employeeId", "issueType", "op", "suggestion"],
        "allOf": [
            {
                "if": {"properties": {"op": {"const": "modify"}}},
                "then": {"required": ["bookingId", "fields"]},
            },
            {
                "if": {"properties": {"op": {"const": "append"}}},
                "then": {"required": ["adjustment"]},
            },
        ],
    }
    return {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": suggestion_item,
            }
        },
        "required": ["suggestions"],
    }


def invoke_bedrock(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call Bedrock Converse with forced tool output (Recon eval pattern)."""
    from botocore.exceptions import BotoCoreError, ClientError

    client = _bedrock_client()
    model_id = default_model_id()

    try:
        response = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": 4096, "temperature": 0},
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": TOOL_NAME,
                            "description": (
                                "Emit structured roster remediation rows that close "
                                "coverageDelta per the sketch."
                            ),
                            "inputSchema": {"json": _tool_schema()},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": TOOL_NAME}},
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(
            f"Bedrock converse failed (profile={aws_profile()}, model={model_id}, "
            f"region={default_region()}): {exc}"
        ) from exc

    return _extract_tool_input(response)


def _extract_tool_input(response: dict[str, Any]) -> dict[str, Any]:
    message = response.get("output", {}).get("message", {})
    for block in message.get("content", []):
        tool_use = block.get("toolUse")
        if tool_use and tool_use.get("name") == TOOL_NAME:
            payload = tool_use.get("input")
            if isinstance(payload, dict):
                return payload
    raise RuntimeError(
        f"Bedrock response did not invoke tool {TOOL_NAME!r}. "
        "Run: aws sso login --profile review"
    )


def bedrock_credentials_ok() -> bool:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

        session = boto3.Session(profile_name=aws_profile(), region_name=default_region())
        session.client("sts").get_caller_identity()
        return True
    except (NoCredentialsError, BotoCoreError, ClientError, Exception):
        return False
