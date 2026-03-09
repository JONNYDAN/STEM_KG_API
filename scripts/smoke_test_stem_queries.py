import argparse
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

SAMPLE_CASES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "query": "Hãy cho tôi biết vòng đời của con bọ rùa diễn ra như thế nào?",
        "topic": "ladybug life cycle",
    },
    {
        "id": 2,
        "query": "Vòng tuần hoàn nước có các quy trình như thế nào?",
        "topic": "water cycle",
    },
    {
        "id": 3,
        "query": "Hệ mặt trời là gì vậy?",
        "topic": "solar system",
    },
    {
        "id": 4,
        "query": "Bạn cho tôi một hình ảnh cấu trúc của núi lửa được không?",
        "topic": "volcano structure",
    },
    {
        "id": 5,
        "query": "Thông tin về Nhật thực",
        "topic": "solar eclipse",
    },
    {
        "id": 6,
        "query": "Các phần của hoa",
        "topic": "parts of flower",
    },
    {
        "id": 7,
        "query": "Chân của con gà với con vịt như thế nào",
        "topic": "chicken leg duck leg",
    },
    {
        "id": 8,
        "query": "Làm sao để vẽ mạch điện",
        "topic": "electric circuit",
    },
    {
        "id": 9,
        "query": "Qúa trình quang hợp diễn ra làm sao?",
        "topic": "photosynthesis",
    },
    {
        "id": 10,
        "query": "Sao con thỏ ăn cỏ và cáo ăn thỏ, mà thỏ lại không ăn cáo",
        "topic": "food chain rabbit fox grass",
    },
]


def _post_query(
    base_url: str,
    query_text: str,
    user_id: str,
    image_path: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/integration/query"
    fields = {
        "query_text": query_text,
        "user_id": user_id,
    }

    image_bytes: Optional[bytes] = None
    image_name: Optional[str] = None
    if image_path and os.path.exists(image_path):
        image_name = os.path.basename(image_path)
        with open(image_path, "rb") as fp:
            image_bytes = fp.read()

    boundary = f"----stem-smoke-{uuid.uuid4().hex}"
    body_chunks: List[bytes] = []

    for key, value in fields.items():
        body_chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    if image_bytes is not None and image_name:
        body_chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="image"; '
                    f'filename="{image_name}"\r\n'
                ).encode("utf-8"),
                b"Content-Type: application/octet-stream\r\n\r\n",
                image_bytes,
                b"\r\n",
            ]
        )

    body_chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(body_chunks)

    request_obj = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(request_obj, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except HTTPError as http_ex:
        detail = http_ex.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {http_ex.code}: {detail}") from http_ex
    except URLError as url_ex:
        raise RuntimeError(f"Network error: {url_ex.reason}") from url_ex


def _compact_result(case: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    query_meta = payload.get("query") or {}
    final_output = payload.get("final_output") or {}
    model_output = payload.get("model_output") or {}
    pending = payload.get("pending_review")

    diagram = final_output.get("diagram") or {}
    has_diagram = bool(diagram.get("diagram_id"))

    status = "diagram_found" if has_diagram else "no_diagram_match"
    if pending and pending.get("status") == "pending":
        status = "pending_learning"

    return {
        "id": case["id"],
        "topic": case["topic"],
        "query": case["query"],
        "status": status,
        "routing_mode": query_meta.get("routing_mode"),
        "phase": query_meta.get("phase"),
        "analysis_case": query_meta.get("analysis_case") or model_output.get("analysis_case"),
        "diagram_id": diagram.get("diagram_id"),
        "description": (final_output.get("description") or "")[:220],
        "pending_item_id": pending.get("_id") if pending else None,
    }


def run_smoke_test(base_url: str, user_id: str, image_path: Optional[str]) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for case in SAMPLE_CASES:
        try:
            payload = _post_query(
                base_url=base_url,
                query_text=case["query"],
                user_id=user_id,
                image_path=image_path,
            )
            reports.append(_compact_result(case, payload))
        except Exception as ex:
            reports.append(
                {
                    "id": case["id"],
                    "topic": case["topic"],
                    "query": case["query"],
                    "status": "error",
                    "error": str(ex),
                }
            )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test 10 STEM query samples")
    parser.add_argument("--base-url", default="http://localhost:8000", help="STEM_KG_API base URL")
    parser.add_argument("--user-id", default="smoke-test-user", help="User id used in query logs")
    parser.add_argument(
        "--image-path",
        default=None,
        help="Optional image path to attach to all queries (simulate multimodal phase)",
    )
    parser.add_argument(
        "--output",
        default="smoke_test_report.json",
        help="Output JSON report path",
    )
    args = parser.parse_args()

    results = run_smoke_test(
        base_url=args.base_url,
        user_id=args.user_id,
        image_path=args.image_path,
    )

    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(results, fp, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("STEM Query Smoke Test Summary")
    print("=" * 80)
    for item in results:
        print(
            f"[{item.get('id')}] {item.get('status')} | "
            f"routing={item.get('routing_mode')} | "
            f"case={item.get('analysis_case')} | "
            f"diagram={item.get('diagram_id')}"
        )
    print("=" * 80)
    print(f"Saved report: {args.output}")


if __name__ == "__main__":
    main()
