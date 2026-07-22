"""Seed a published+indexed doc for F06 chat e2e (F04temp).

Usage (API running, auth stub or cookie as needed):

  cd apps/api
  python -m scripts.seed_f04temp_kb \\
    --host tenant-a.lxzxai.com \\
    --user-id <uuid> \\
    --base-url http://127.0.0.1:8000

Or with AUTH_STUB_ENABLED=true and NEXT_PUBLIC_DEV_USER_ID.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

# Allow running as `python -m scripts.seed_f04temp_kb` from apps/api
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_API_ROOT / "src"))


SAMPLE = """退货政策

客户可在收货后 30 天内申请退货。
退货商品须保持原包装完好。
超过 30 天窗口的申请将不予受理。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed F04temp knowledge for F06 e2e")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="tenant-a.lxzxai.com")
    parser.add_argument("--user-id", required=True, help="X-Test-User-Id (AUTH_STUB)")
    args = parser.parse_args()

    headers = {
        "Host": args.host,
        "X-Test-User-Id": args.user_id,
        "Accept": "application/json",
    }
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=60.0) as client:
        r = client.post("/v1/documents")
        r.raise_for_status()
        doc_id = r.json()["id"]
        print("created", doc_id)

        files = {"file": ("return-policy.txt", SAMPLE.encode("utf-8"), "text/plain")}
        r = client.post(f"/v1/documents/{doc_id}/files", files=files)
        r.raise_for_status()
        print("uploaded file")

        r = client.patch(
            f"/v1/documents/{doc_id}",
            json={"title": "退货政策", "tag": "faq"},
        )
        r.raise_for_status()
        print("saved draft")

        r = client.post(f"/v1/documents/{doc_id}/submit-review")
        r.raise_for_status()
        print("review")

        r = client.post(f"/v1/documents/{doc_id}/publish")
        r.raise_for_status()
        print("published (index sync if INDEX_SYNC_ON_PUBLISH=true)")

        r = client.get(f"/v1/documents/{doc_id}/index-status")
        r.raise_for_status()
        print("index-status", r.json())


if __name__ == "__main__":
    main()
