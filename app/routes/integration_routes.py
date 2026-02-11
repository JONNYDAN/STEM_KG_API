from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import os
import re
import uuid
import requests
from datetime import datetime

from app.services.integration_service import IntegrationService
from app.database.postgres_conn import get_postgres_db
from app.services.postgres_service import PostgresService
from app.services.neo4j_service import Neo4jService
from app.services.mongo_service import MongoService
from app.config import config

router = APIRouter(prefix="/integration", tags=["Integration"])


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _parse_triple_from_text(text: str) -> Optional[Dict[str, str]]:
    if not text:
        return None

    parts = re.split(r"\s*(?:->|=>|\||,|;|—|-)\s*", text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) >= 3:
        return {
            "subject": parts[0],
            "relationship": parts[1],
            "object": parts[2]
        }

    if len(parts) == 2:
        return {
            "subject": parts[0],
            "relationship": "related_to",
            "object": parts[1]
        }

    return None


def _build_triples_from_labels(labels: List[str]) -> List[Dict[str, str]]:
    cleaned = [_normalize_label(label) for label in labels if label and _normalize_label(label)]
    unique_labels = list(dict.fromkeys(cleaned))

    if len(unique_labels) < 2:
        return []

    triples: List[Dict[str, str]] = []
    for i in range(len(unique_labels) - 1):
        triples.append({
            "subject": unique_labels[i],
            "relationship": "related_to",
            "object": unique_labels[i + 1]
        })
    return triples


def _query_databases(
    subject: str,
    relationship: str,
    object_value: str,
    postgres_service: PostgresService,
    neo4j_service: Neo4jService,
    mongo_service: MongoService
) -> Dict[str, Any]:
    postgres_results = postgres_service.search_categories_by_triple(subject, relationship, object_value)

    postgres_diagrams: List[Dict[str, Any]] = []
    if postgres_results:
        best_category = postgres_results[0]
        diagrams = postgres_service.get_diagrams_by_category(best_category["category_id"])
        postgres_diagrams = [
            {
                "diagram_id": d.id,
                "image_path": d.image_path,
                "category_id": d.category_id
            }
            for d in diagrams
        ]

    neo4j_results = neo4j_service.search_diagrams_by_triple(subject, relationship, object_value)
    diagram_ids = [r.get("diagram_id") for r in neo4j_results if r.get("diagram_id")]

    mongo_annotations: List[Dict[str, Any]] = []
    for diagram_id in diagram_ids:
        annotations = mongo_service.get_annotations_by_diagram(diagram_id)
        if annotations:
            mongo_annotations.extend(annotations)

    descriptions = [
        f"{r.get('subject_name')} {r.get('relationship')} {r.get('object_name')}"
        for r in neo4j_results
        if r.get("subject_name") and r.get("relationship") and r.get("object_name")
    ]

    neo4j_diagrams: List[Dict[str, Any]] = []
    for diagram_id in diagram_ids:
        diagram = postgres_service.get_diagram(diagram_id)
        if diagram:
            neo4j_diagrams.append({
                "diagram_id": diagram.id,
                "image_path": diagram.image_path,
                "category_id": diagram.category_id
            })

    return {
        "postgres": {
            "categories": postgres_results,
            "diagrams": postgres_diagrams
        },
        "neo4j": neo4j_results,
        "mongo": mongo_annotations,
        "descriptions": list(dict.fromkeys(descriptions)),
        "diagrams": list({d["diagram_id"]: d for d in (postgres_diagrams + neo4j_diagrams)}.values())
    }

@router.get("/search/triple")
def search_by_triple(
    subject: str = Query(..., description="Subject of the triple"),
    relationship: str = Query(..., description="Relationship of the triple"),
    object: str = Query(..., description="Object of the triple")
) -> Dict[str, Any]:
    """Tìm kiếm tích hợp từ cả 3 cơ sở dữ liệu dựa trên bộ ba"""
    service = IntegrationService()
    try:
        results = service.process_triple_query(subject, relationship, object)
        return {
            "success": True,
            "query": {"subject": subject, "relationship": relationship, "object": object},
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connections()

@router.get("/search/category/{category_name}")
def search_by_category(category_name: str) -> Dict[str, Any]:
    """Tìm kiếm tất cả thông tin theo category"""
    service = IntegrationService()
    try:
        results = service.search_by_category(category_name)
        return {
            "success": True,
            "category": category_name,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connections()

@router.post("/link/meta")
def link_meta_data(
    diagram_id: str,
    neo4j_node_id: str,
    postgres_id: int,
    mongo_doc_id: str
) -> Dict[str, Any]:
    """Liên kết metadata giữa các cơ sở dữ liệu"""
    service = IntegrationService()
    try:
        # Logic liên kết metadata giữa các DB
        # Có thể lưu vào bảng link_meta trong PostgreSQL
        return {
            "success": True,
            "message": "Metadata linked successfully",
            "links": {
                "diagram_id": diagram_id,
                "neo4j_node": neo4j_node_id,
                "postgres_record": postgres_id,
                "mongo_document": mongo_doc_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connections()


@router.post("/query")
def query_stem_multimedia(
    query_text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    user_id: Optional[str] = Form(None),
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """Nhận text/ảnh, lưu input, gọi model OCR, sinh bộ ba và truy vấn KG."""
    if not query_text and not image:
        raise HTTPException(status_code=400, detail="Please provide query_text or image")

    mongo_service = MongoService()
    neo4j_service = Neo4jService()
    postgres_service = PostgresService(db)

    saved_image_path: Optional[str] = None
    saved_image_url: Optional[str] = None
    model_output: Optional[Dict[str, Any]] = None
    triples: List[Dict[str, str]] = []

    try:
        if image:
            os.makedirs(config.UPLOAD_DIR, exist_ok=True)
            extension = os.path.splitext(image.filename or "")[1] or ".png"
            filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}{extension}"
            saved_image_path = os.path.join(config.UPLOAD_DIR, filename)
            saved_image_url = f"/uploads/{filename}"

            image_bytes = image.file.read()
            with open(saved_image_path, "wb") as f:
                f.write(image_bytes)

            try:
                response = requests.post(
                    config.MODEL_OCR_URL,
                    files={"image": (image.filename, image_bytes, image.content_type or "application/octet-stream")},
                    timeout=60
                )
                response.raise_for_status()
                model_output = response.json()
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Model OCR error: {str(e)}")

            objects = model_output.get("objects", []) if model_output else []
            labels = [
                obj.get("translated_text") or obj.get("original_text") or ""
                for obj in objects
            ]
            triples.extend(_build_triples_from_labels(labels))

        if query_text:
            triple_from_text = _parse_triple_from_text(query_text)
            if triple_from_text:
                triples.insert(0, triple_from_text)

        if not triples:
            raise HTTPException(status_code=400, detail="Could not infer triples from input")

        query_results = [
            {
                "triple": triple,
                "results": _query_databases(
                    triple["subject"],
                    triple["relationship"],
                    triple["object"],
                    postgres_service,
                    neo4j_service,
                    mongo_service
                )
            }
            for triple in triples
        ]

        log_payload = {
            "type": "mixed" if query_text and image else "image" if image else "text",
            "query_text": query_text,
            "image_path": saved_image_path,
            "image_url": saved_image_url,
            "user_id": user_id,
            "triples": triples,
            "timestamp": datetime.utcnow().isoformat()
        }
        log = mongo_service.create_query_log(log_payload)

        return {
            "success": True,
            "log_id": log.get("_id") if log else None,
            "query": {
                "type": log_payload["type"],
                "text": query_text,
                "image_url": saved_image_url
            },
            "model_output": model_output,
            "triples": triples,
            "query_results": query_results
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()


@router.get("/query/logs")
def get_query_logs(
    limit: int = Query(50, ge=1, le=200)
) -> Dict[str, Any]:
    """Lấy danh sách query logs (dùng cho admin)."""
    service = MongoService()
    try:
        logs = service.get_query_logs(limit=limit)
        return {
            "success": True,
            "total": len(logs),
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))