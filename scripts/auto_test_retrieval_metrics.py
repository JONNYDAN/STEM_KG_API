import argparse
import json
import os
import statistics
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


def _normalize_id(value: Any) -> str:
    return str(value or "").strip().lower()


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        normalized = _normalize_id(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _precision_at_k(predicted: List[str], relevant: Set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = predicted[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in relevant)
    return hits / float(k)


def _recall_at_k(predicted: List[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = predicted[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / float(len(relevant))


def _f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _average_precision_at_k(predicted: List[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0

    score_sum = 0.0
    hit_count = 0
    for rank, item in enumerate(predicted[:k], start=1):
        if item in relevant:
            hit_count += 1
            score_sum += hit_count / float(rank)

    return score_sum / float(len(relevant))


def _extract_ranked_diagrams_from_payload(payload: Dict[str, Any]) -> List[str]:
    ranked_ids: List[str] = []

    final_output = payload.get("final_output") or {}
    primary = (final_output.get("diagram") or {}).get("diagram_id")
    if primary:
        ranked_ids.append(str(primary))

    for item in payload.get("query_results") or []:
        results = item.get("results") or {}

        for diagram in results.get("diagrams") or []:
            diagram_id = diagram.get("diagram_id") or diagram.get("id")
            if diagram_id:
                ranked_ids.append(str(diagram_id))

        postgres = results.get("postgres") or {}
        for diagram in postgres.get("diagrams") or []:
            diagram_id = diagram.get("diagram_id") or diagram.get("id")
            if diagram_id:
                ranked_ids.append(str(diagram_id))

    return _unique_preserve_order(ranked_ids)


def _post_query(
    base_url: str,
    query_text: str,
    user_id: str,
    analysis_mode: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/integration/query"
    fields = {
        "query_text": query_text,
        "user_id": user_id,
        "analysis_mode": analysis_mode,
    }

    boundary = f"----stem-metrics-{uuid.uuid4().hex}"
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


def _load_qrels(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fp:
        raw = json.load(fp)

    if not isinstance(raw, list):
        raise ValueError("Qrels file must be a JSON array")

    qrels: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue

        qid = _normalize_id(item.get("id") or item.get("query_id") or idx)
        query_text = str(item.get("query") or item.get("query_text") or "").strip()

        relevant_ids = item.get("relevant_diagram_ids") or item.get("relevant_ids") or []
        if not isinstance(relevant_ids, list):
            raise ValueError(f"Invalid relevant list at qid={qid}")

        qrels.append(
            {
                "id": qid,
                "query": query_text,
                "relevant": set(_unique_preserve_order([str(v) for v in relevant_ids])),
            }
        )

    if not qrels:
        raise ValueError("No qrels entries found")

    return qrels


def _load_predictions(path: str) -> Dict[str, List[str]]:
    with open(path, "r", encoding="utf-8") as fp:
        raw = json.load(fp)

    if not isinstance(raw, list):
        raise ValueError("Predictions file must be a JSON array")

    predictions: Dict[str, List[str]] = {}

    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue

        qid = _normalize_id(item.get("id") or item.get("query_id") or idx)
        ranked = (
            item.get("predicted_diagram_ids")
            or item.get("ranked_diagram_ids")
            or item.get("diagram_ids")
            or []
        )

        if isinstance(ranked, str):
            ranked = [ranked]
        if not isinstance(ranked, list):
            ranked = []

        top1 = item.get("diagram_id")
        if top1 and (not ranked or _normalize_id(top1) != _normalize_id(ranked[0])):
            ranked = [str(top1)] + [str(v) for v in ranked]

        predictions[qid] = _unique_preserve_order([str(v) for v in ranked])

    return predictions


def _run_live_predictions(
    base_url: str,
    qrels: List[Dict[str, Any]],
    user_id: str,
    analysis_mode: str,
    timeout: int,
) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    predictions: Dict[str, List[str]] = {}
    traces: List[Dict[str, Any]] = []

    for entry in qrels:
        qid = entry["id"]
        query = entry["query"]

        if not query:
            predictions[qid] = []
            traces.append(
                {
                    "id": qid,
                    "status": "skipped",
                    "reason": "missing query text",
                }
            )
            continue

        try:
            payload = _post_query(
                base_url=base_url,
                query_text=query,
                user_id=user_id,
                analysis_mode=analysis_mode,
                timeout=timeout,
            )
            ranked = _extract_ranked_diagrams_from_payload(payload)
            predictions[qid] = ranked
            traces.append(
                {
                    "id": qid,
                    "status": "ok",
                    "routing_mode": (payload.get("query") or {}).get("routing_mode"),
                    "phase": (payload.get("query") or {}).get("phase"),
                    "predicted_diagram_ids": ranked,
                }
            )
        except Exception as ex:
            predictions[qid] = []
            traces.append(
                {
                    "id": qid,
                    "status": "error",
                    "error": str(ex),
                    "predicted_diagram_ids": [],
                }
            )

    return predictions, traces


def _evaluate(
    qrels: List[Dict[str, Any]],
    predictions: Dict[str, List[str]],
    top_k: int,
) -> Dict[str, Any]:
    per_query: List[Dict[str, Any]] = []

    precisions: List[float] = []
    recalls: List[float] = []
    f1_scores: List[float] = []
    ap_scores: List[float] = []

    for entry in qrels:
        qid = entry["id"]
        relevant: Set[str] = entry["relevant"]
        predicted = _unique_preserve_order(predictions.get(qid, []))

        precision = _precision_at_k(predicted, relevant, top_k)
        recall = _recall_at_k(predicted, relevant, top_k)
        f1 = _f1_score(precision, recall)
        ap = _average_precision_at_k(predicted, relevant, top_k)

        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
        ap_scores.append(ap)

        per_query.append(
            {
                "id": qid,
                "query": entry["query"],
                "relevant_diagram_ids": sorted(list(relevant)),
                "predicted_diagram_ids": predicted,
                f"precision@{top_k}": round(precision, 6),
                f"recall@{top_k}": round(recall, 6),
                f"f1@{top_k}": round(f1, 6),
                f"ap@{top_k}": round(ap, 6),
            }
        )

    summary = {
        "queries_count": len(qrels),
        f"macro_precision@{top_k}": round(statistics.mean(precisions) if precisions else 0.0, 6),
        f"macro_recall@{top_k}": round(statistics.mean(recalls) if recalls else 0.0, 6),
        f"macro_f1@{top_k}": round(statistics.mean(f1_scores) if f1_scores else 0.0, 6),
        f"map@{top_k}": round(statistics.mean(ap_scores) if ap_scores else 0.0, 6),
    }

    return {
        "summary": summary,
        "per_query": per_query,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Auto-test retrieval quality with Precision/Recall/F1/MAP. "
            "Use --predictions-file for offline evaluation, or provide --base-url "
            "to call the live API directly."
        )
    )
    parser.add_argument("--qrels", required=True, help="Path to qrels JSON file")
    parser.add_argument(
        "--predictions-file",
        default=None,
        help="Optional path to predictions JSON. If omitted, tool calls API with --base-url",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API base URL (required when --predictions-file is not provided)",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Cutoff K for P/R/F1/AP")
    parser.add_argument("--analysis-mode", default="gemini", choices=["basic", "gemini"])
    parser.add_argument("--user-id", default="metrics-test-user")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", default="metrics_report.json", help="Output report JSON path")
    args = parser.parse_args()

    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")

    qrels = _load_qrels(args.qrels)

    traces: List[Dict[str, Any]] = []
    if args.predictions_file:
        predictions = _load_predictions(args.predictions_file)
    else:
        if not args.base_url:
            raise ValueError("Provide --base-url when --predictions-file is not used")
        predictions, traces = _run_live_predictions(
            base_url=args.base_url,
            qrels=qrels,
            user_id=args.user_id,
            analysis_mode=args.analysis_mode,
            timeout=args.timeout,
        )

    evaluation = _evaluate(qrels=qrels, predictions=predictions, top_k=args.top_k)

    report = {
        "config": {
            "qrels": os.path.abspath(args.qrels),
            "predictions_file": os.path.abspath(args.predictions_file) if args.predictions_file else None,
            "base_url": args.base_url,
            "top_k": args.top_k,
            "analysis_mode": args.analysis_mode,
            "user_id": args.user_id,
            "timeout": args.timeout,
        },
        "metrics": evaluation["summary"],
        "per_query": evaluation["per_query"],
        "live_run_traces": traces,
    }

    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("Retrieval Metrics Summary")
    print("=" * 80)
    for key, value in report["metrics"].items():
        print(f"{key}: {value}")
    print("=" * 80)
    print(f"Saved report: {args.output}")


if __name__ == "__main__":
    main()
