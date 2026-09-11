"""Export records from a Feishu Bitable using environment-provided credentials."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from urllib.error import HTTPError


def request_json(method: str, url: str, payload: dict | None = None, token: str | None = None) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
            raise RuntimeError(f"Feishu HTTP {exc.code}: code={detail.get('code')} msg={detail.get('msg', 'unknown')}") from exc
        except json.JSONDecodeError:
            raise RuntimeError(f"Feishu HTTP {exc.code}: {body[:300]}") from exc
    if result.get("code", 0) != 0:
        raise RuntimeError(f"Feishu API error {result.get('code')}: {result.get('msg', 'unknown')}")
    return result


def main() -> None:
    api_base = os.getenv("FEISHU_API_BASE", "https://open.feishu.cn").rstrip("/")
    app_id = os.environ["FEISHU_APP_ID"]
    app_secret = os.environ["FEISHU_APP_SECRET"]
    base_token = os.environ["FEISHU_BASE_TOKEN"]
    table_id = os.environ["FEISHU_TABLE_ID"]
    output_path = os.getenv("FEISHU_EXPORT_PATH", "feishu-bitable-records.json")

    token_result = request_json(
        "POST",
        f"{api_base}/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    tenant_token = token_result["tenant_access_token"]
    records: list[dict] = []
    page_token = ""
    while True:
        params = {"page_size": "500"}
        if page_token:
            params["page_token"] = page_token
        url = f"{api_base}/open-apis/bitable/v1/apps/{urllib.parse.quote(base_token, safe='')}/tables/{urllib.parse.quote(table_id, safe='')}/records?{urllib.parse.urlencode(params)}"
        page = request_json("GET", url, token=tenant_token)
        data = page.get("data") or {}
        records.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
        if not page_token:
            raise RuntimeError("Feishu returned has_more without page_token")
    result = {"source": {"base_token": base_token, "table_id": table_id}, "record_count": len(records), "records": records}
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "record_count": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
