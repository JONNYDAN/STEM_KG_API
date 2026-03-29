from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import re
import json
import uuid
import time
import requests
import unicodedata
from datetime import datetime
from urllib.parse import quote_plus

from app.services.integration_service import IntegrationService
from app.database.postgres_conn import get_postgres_db
from app.services.postgres_service import PostgresService
from app.services.neo4j_service import Neo4jService
from app.services.mongo_service import MongoService
from app.schemas import postgres_schemas as postgres_schemas
from app.schemas.mongo_schemas import SemanticRelationshipCreate
from app.config import config

router = APIRouter(prefix="/integration", tags=["Integration"])

VI_EN_PHRASE_MAP = {
    "hay cho toi biet": "tell me",
    "cho toi biet": "tell me",
    "la gi": "what is",
    "nam o dau": "where located",
    "o dau": "where",
    "vong doi": "life cycle",
    "ech": "frog",
    "trung": "egg",
    "nong noc": "tadpole",
    "ech con": "froglet",
    "proton": "proton",
    "neutron": "neutron",
    "electron": "electron",
    "hat nhan": "nucleus",
    "nguyen tu": "atom",
}

VI_FILLER_WORDS = {
    "hay", "toi", "cho", "biet", "duoc", "khong", "voi", "ve", "mot", "nhung", "cac",
    "la", "gi", "o", "dau", "nam", "tai", "the", "nao", "xin", "vui", "long"
}

EN_FILLER_WORDS = {
    "tell", "me", "what", "is", "where", "located", "about", "please", "show", "explain",
    "the", "a", "an", "of", "to", "in", "for", "on", "and",
    "can", "could", "would", "you", "your", "how", "works", "work", "does", "do",
    "voi", "chan", "ma", "lai", "sao", "thong", "tin", "info", "dien", "ra"
}

GENERIC_SUBJECT_TERMS = {
    "life", "cycle", "diagram", "process", "stage", "stages", "system", "overview", "related", "query"
}

SUBJECT_SPELLING_NORMALIZATION = {
    "laydybug": "ladybug",
    "lady bug": "ladybug",
    "bo rua": "ladybug",
    "chuon chuon": "dragonfly",
}

VIDEO_QUERY_STOPWORDS = EN_FILLER_WORDS.union(VI_FILLER_WORDS).union(GENERIC_SUBJECT_TERMS).union({
    "stem", "science", "education", "video", "youtube", "related", "query"
})

LOW_SIGNAL_VIDEO_TOKENS = {
    "cross", "section", "figure", "fig", "label", "labels", "part", "parts",
    "step", "steps", "phase", "stages", "stage", "subject", "intersection",
    "textlabel", "schema", "view", "image", "picture",
}


def _video_query_priority_score(phrase: str) -> float:
    tokens = [token for token in _normalize_label(phrase).split() if token]
    if not tokens:
        return -100.0

    info_tokens = [
        token
        for token in tokens
        if token not in VIDEO_QUERY_STOPWORDS
        and token not in LOW_SIGNAL_VIDEO_TOKENS
        and len(token) >= 3
    ]
    low_signal_hits = [token for token in tokens if token in LOW_SIGNAL_VIDEO_TOKENS]
    short_hits = [token for token in tokens if len(token) <= 1]

    score = 0.0
    score += len(info_tokens) * 3.0
    score += min(len(tokens), 4) * 0.25
    score -= len(low_signal_hits) * 1.5
    score -= len(short_hits) * 2.0

    if len(info_tokens) == 0:
        score -= 3.0

    return score


def _strip_accents(text: str) -> str:
    value = "".join(c for c in unicodedata.normalize("NFD", text or "") if unicodedata.category(c) != "Mn")
    return value.replace("đ", "d").replace("Đ", "D")


def _normalize_prompt_to_english(prompt: str) -> str:
    raw = (prompt or "").strip().lower()
    raw = re.sub(r"[^\w\s]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()

    no_accent = _strip_accents(raw)
    translated = no_accent
    for vi_phrase, en_phrase in sorted(VI_EN_PHRASE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        translated = re.sub(rf"\b{re.escape(vi_phrase)}\b", en_phrase, translated)

    translated = re.sub(r"\s+", " ", translated).strip()
    if not translated:
        return ""

    tokens = [
        token for token in translated.split()
        if token not in VI_FILLER_WORDS
    ]
    return " ".join(tokens)


def _extract_keyword_candidates(normalized_en_prompt: str) -> List[str]:
    tokens = [
        token for token in (normalized_en_prompt or "").split()
        if token and token not in EN_FILLER_WORDS and len(token) >= 3
    ]

    if not tokens:
        return []

    candidates = [" ".join(tokens)]
    for size in [3, 2, 1]:
        if len(tokens) < size:
            continue
        for i in range(len(tokens) - size + 1):
            candidates.append(" ".join(tokens[i:i + size]))

    return list(dict.fromkeys(candidates))


def _extract_subject_term(normalized_en_prompt: str) -> str:
    tokens = [
        token for token in (normalized_en_prompt or "").split()
        if token and token not in EN_FILLER_WORDS
    ]
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    return " ".join(tokens)


def _extract_subject_candidates(normalized_en_prompt: str) -> List[str]:
    term = _extract_subject_term(normalized_en_prompt)
    if not term:
        return []

    tokens = [token for token in term.split() if token]
    normalized_tokens = [SUBJECT_SPELLING_NORMALIZATION.get(token, token) for token in tokens]

    specific_tokens = [
        token for token in normalized_tokens
        if len(token) >= 3 and token not in EN_FILLER_WORDS and token not in GENERIC_SUBJECT_TERMS
    ]

    candidates: List[str] = []
    candidates.extend(specific_tokens)

    # Keep useful bigrams only when at least one token is specific (e.g., "ladybug cycle").
    for size in [2]:
        if len(normalized_tokens) < size:
            continue
        for i in range(len(normalized_tokens) - size + 1):
            gram_tokens = normalized_tokens[i:i + size]
            if all(token in GENERIC_SUBJECT_TERMS for token in gram_tokens):
                continue
            phrase = " ".join(gram_tokens)
            candidates.append(phrase)

    normalized_term = " ".join(normalized_tokens)
    if normalized_term and not all(token in GENERIC_SUBJECT_TERMS for token in normalized_tokens):
        candidates.append(normalized_term)

    return list(dict.fromkeys([candidate for candidate in candidates if candidate]))


def _is_valid_subject_candidate(term: str) -> bool:
    normalized = _normalize_label(term)
    if not normalized:
        return False
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return False

    informative_tokens = [
        token for token in tokens
        if token not in EN_FILLER_WORDS and token not in GENERIC_SUBJECT_TERMS and len(token) >= 4
    ]
    return bool(informative_tokens)


def _collect_diagrams_from_categories(postgres_service: PostgresService, category_ids: List[int], max_diagrams: int = 500) -> List[Dict[str, Any]]:
    diagrams: List[Dict[str, Any]] = []
    diagram_seen = set()

    for category_id in category_ids:
        for diagram in postgres_service.get_diagrams_by_category(category_id):
            if diagram.id in diagram_seen:
                continue
            diagram_seen.add(diagram.id)
            diagrams.append(_serialize_diagram(diagram))
            if len(diagrams) >= max_diagrams:
                return diagrams

    return diagrams


def _first_diagram(diagrams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not diagrams:
        return []
    return [diagrams[0]]


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _safe_terms(values: Optional[List[str]]) -> List[str]:
    terms = []
    for value in values or []:
        normalized = _normalize_label(value)
        if normalized:
            terms.append(normalized)
    return list(dict.fromkeys(terms))


def _normalize_analysis_mode(value: Optional[str]) -> str:
    mode = _normalize_label(value or "")
    if mode not in {"basic", "gemini"}:
        return "gemini"
    return mode


def _serialize_diagram(diagram: Any) -> Dict[str, Any]:
    if not diagram:
        return {}

    if isinstance(diagram, dict):
        return {
            "diagram_id": diagram.get("diagram_id") or diagram.get("id"),
            "image_path": diagram.get("image_path"),
            "category_id": diagram.get("category_id"),
            "description": diagram.get("description"),
            "path_pdf": diagram.get("path_pdf") or diagram.get("pdf_path"),
        }

    return {
        "diagram_id": getattr(diagram, "id", None),
        "image_path": getattr(diagram, "image_path", None),
        "category_id": getattr(diagram, "category_id", None),
        "description": getattr(diagram, "description", None),
        "path_pdf": getattr(diagram, "path_pdf", None),
    }


def _collect_annotation_terms(annotation: Any) -> List[str]:
    terms: List[str] = []
    if isinstance(annotation, dict):
        for key, value in annotation.items():
            if key.lower() in {"label", "labels", "text", "name", "title", "translated_text", "original_text"}:
                if isinstance(value, list):
                    terms.extend([str(item) for item in value if item])
                elif value:
                    terms.append(str(value))
            else:
                terms.extend(_collect_annotation_terms(value))
    elif isinstance(annotation, list):
        for item in annotation:
            terms.extend(_collect_annotation_terms(item))
    return terms


def _diagram_matches_subjects(diagram_id: str, subject_terms: List[str], mongo_service: MongoService) -> bool:
    if not subject_terms:
        return True
    annotations = mongo_service.get_annotations_by_diagram(diagram_id)
    if not annotations:
        return False

    flattened_terms = _safe_terms(_collect_annotation_terms(annotations))
    return any(
        subject_term in term or term in subject_term
        for subject_term in subject_terms
        for term in flattened_terms
    )


def _diagram_lookup_keys(diagram: Dict[str, Any]) -> List[str]:
    keys: List[str] = []

    diagram_id = str(diagram.get("diagram_id") or "").strip().lower()
    if diagram_id:
        keys.append(diagram_id)
        keys.append(re.sub(r"\.(png|jpg|jpeg|webp)$", "", diagram_id))

    image_path = str(diagram.get("image_path") or "").strip().lower()
    if image_path:
        image_name = os.path.basename(image_path)
        keys.append(image_name)
        keys.append(re.sub(r"\.(png|jpg|jpeg|webp)$", "", image_name))

    cleaned = [key for key in keys if key]
    return list(dict.fromkeys(cleaned))


def _select_by_neo4j_textlabels(
    neo4j_service: Neo4jService,
    diagrams: List[Dict[str, Any]],
    subject_terms: List[str],
    normalized_query_text: Optional[str],
    category_name: Optional[str],
) -> List[Dict[str, Any]]:
    if not diagrams:
        return []

    term_candidates = _safe_terms(subject_terms)
    term_candidates.extend(_derive_subject_terms_from_text(normalized_query_text or ""))
    term_candidates = list(dict.fromkeys([term for term in term_candidates if term]))
    if not term_candidates:
        return []

    query_phrases = _extract_query_phrases(normalized_query_text or "")
    normalized_query_blob = _normalize_label(normalized_query_text or "")
    specific_terms = [
        term
        for term in term_candidates
        if term not in GENERIC_SUBJECT_TERMS and term not in EN_FILLER_WORDS and len(term) >= 4
    ]
    strict_subject_required = bool(specific_terms)
    if "life cycle" in normalized_query_blob:
        specific_subject_terms = [
            term
            for term in term_candidates
            if term and term not in GENERIC_SUBJECT_TERMS and " " not in term
        ]
        for subject_term in specific_subject_terms:
            query_phrases.append(f"{subject_term} life cycle")
            query_phrases.append(f"life cycle {subject_term}")
    query_phrases = list(dict.fromkeys([phrase for phrase in query_phrases if phrase]))

    diagram_key_map: Dict[str, str] = {}
    lookup_keys: List[str] = []
    for diagram in diagrams:
        canonical_id = str(diagram.get("diagram_id") or "").strip()
        for key in _diagram_lookup_keys(diagram):
            diagram_key_map[key] = canonical_id
            lookup_keys.append(key)
    lookup_keys = list(dict.fromkeys([key for key in lookup_keys if key]))
    if not lookup_keys:
        return []

    cypher = """
    UNWIND $keys AS lookup_key
    MATCH (tl)
    WHERE (
            any(lbl IN labels(tl) WHERE toLower(lbl) = 'textlabel')
            OR toLower(coalesce(tl.type, '')) IN ['text_label', 'textlabel']
        )
        AND (
            toLower(coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, '')) = lookup_key
            OR replace(toLower(coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, '')), '.png', '') = lookup_key
            OR replace(toLower(coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, '')), '.jpg', '') = lookup_key
            OR replace(toLower(coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, '')), '.jpeg', '') = lookup_key
        )
    RETURN coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, '') AS diagram_id,
                 coalesce(tl.value, tl.text, tl.label, tl.name, '') AS value,
                 coalesce(tl.replacement_text, tl.replacementText, '') AS replacement_text,
                 coalesce(tl.category, tl.category_name, tl.categoryName, '') AS category
    """

    try:
        records = neo4j_service.session.run(cypher, keys=lookup_keys)
    except Exception:
        return []

    diagram_scores: Dict[str, float] = {}
    normalized_category = _normalize_label(category_name or "")
    for record in records:
        diagram_id_raw = _normalize_label(record.get("diagram_id", ""))
        key = re.sub(r"\.(png|jpg|jpeg|webp)$", "", diagram_id_raw)
        canonical_id = diagram_key_map.get(diagram_id_raw) or diagram_key_map.get(key)
        if not canonical_id:
            continue

        text_blob = _normalize_label(f"{record.get('value', '')} {record.get('replacement_text', '')}")
        if not text_blob:
            continue

        score = 0.0
        matched_specific = False
        for term in term_candidates:
            if term in text_blob:
                score += 3.0
                if term in specific_terms:
                    matched_specific = True
            elif any(token in text_blob for token in term.split() if len(token) >= 3):
                score += 1.0
                if term in specific_terms:
                    matched_specific = True

        for phrase in query_phrases:
            if phrase in text_blob:
                score += 6.0

        for term in term_candidates:
            if term in GENERIC_SUBJECT_TERMS:
                continue
            combined_phrase = f"{term} life cycle"
            if combined_phrase in text_blob:
                score += 10.0
                if term in specific_terms:
                    matched_specific = True

        if strict_subject_required and not matched_specific:
            continue

        label_category = _normalize_label(record.get("category", ""))
        if normalized_category and label_category and normalized_category in label_category:
            score += 2.0

        if score <= 0:
            continue
        diagram_scores[canonical_id] = diagram_scores.get(canonical_id, 0.0) + score

    if not diagram_scores:
        return []

    ranked = sorted(diagrams, key=lambda item: diagram_scores.get(str(item.get("diagram_id")), 0.0), reverse=True)
    top = ranked[0]
    if diagram_scores.get(str(top.get("diagram_id")), 0.0) <= 0:
        return []
    return [top]


def _search_diagrams_by_subject_textlabels_global(
    neo4j_service: Neo4jService,
    postgres_service: PostgresService,
    subject_terms: List[str],
    normalized_query_text: Optional[str],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    terms = _safe_terms(subject_terms)
    terms.extend(_derive_subject_terms_from_text(normalized_query_text or ""))
    terms = [term for term in list(dict.fromkeys(terms)) if term and term not in GENERIC_SUBJECT_TERMS]
    if not terms:
        return []

    cypher = """
    MATCH (tl)
    WHERE (
        any(lbl IN labels(tl) WHERE toLower(lbl) = 'textlabel')
        OR toLower(coalesce(tl.type, '')) IN ['text_label', 'textlabel']
    )
    WITH tl,
         toLower(trim(coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, ''))) AS diagram_id,
         toLower(trim(
            coalesce(tl.value, '') + ' ' +
            coalesce(tl.replacement_text, '') + ' ' +
            coalesce(tl.text, '') + ' ' +
            coalesce(tl.label, '') + ' ' +
            coalesce(tl.name, '')
         )) AS text_blob
    WHERE diagram_id <> '' AND text_blob <> ''
    RETURN diagram_id, text_blob
    """

    try:
        records = neo4j_service.session.run(cypher)
    except Exception:
        return []

    query_blob = _normalize_label(normalized_query_text or "")
    scored: Dict[str, float] = {}
    for record in records:
        diagram_id_raw = _normalize_label(record.get("diagram_id", ""))
        text_blob = _normalize_label(record.get("text_blob", ""))
        if not diagram_id_raw or not text_blob:
            continue

        score = 0.0
        for term in terms:
            if term in text_blob:
                score += 4.0
            else:
                term_tokens = [token for token in term.split() if len(token) >= 3 and token not in GENERIC_SUBJECT_TERMS]
                score += sum(1.0 for token in term_tokens if token in text_blob)

        if query_blob and query_blob in text_blob:
            score += 3.0

        if score <= 0:
            continue
        scored[diagram_id_raw] = max(scored.get(diagram_id_raw, 0.0), score)

    if not scored:
        return []

    ranked_ids = sorted(scored.keys(), key=lambda diagram_id: scored[diagram_id], reverse=True)[: max(1, limit)]
    results: List[Dict[str, Any]] = []
    for raw_id in ranked_ids:
        candidates = [raw_id]
        if not re.search(r"\.(png|jpg|jpeg|webp)$", raw_id):
            candidates.extend([f"{raw_id}.png", f"{raw_id}.jpg", f"{raw_id}.jpeg", f"{raw_id}.webp"])

        matched = None
        for candidate_id in candidates:
            diagram = postgres_service.get_diagram(candidate_id)
            if diagram:
                matched = _serialize_diagram(diagram)
                break

        if matched:
            results.append(matched)

    return results


def _derive_focus_subject_terms_from_triples(triples: List[Dict[str, str]]) -> List[str]:
    focus: List[str] = []
    relation_terms = {
        "eat", "eats", "consume", "consumes", "feed_on", "feeds_on", "predator_of", "prey_of"
    }

    for triple in triples:
        relation = _normalize_label(triple.get("relationship", ""))
        if relation.startswith("not_"):
            continue

        if relation in relation_terms:
            subject_value = _normalize_label(triple.get("subject", ""))
            object_value = _normalize_label(triple.get("object", ""))
            if subject_value and subject_value not in GENERIC_SUBJECT_TERMS:
                focus.append(subject_value)
            if object_value and object_value not in GENERIC_SUBJECT_TERMS:
                focus.append(object_value)

    if not focus:
        return []

    return list(dict.fromkeys(focus))


def _search_diagram_by_required_subject_terms(
    neo4j_service: Neo4jService,
    postgres_service: PostgresService,
    required_terms: List[str],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    terms = [
        _normalize_label(term)
        for term in required_terms
        if _normalize_label(term) and _normalize_label(term) not in GENERIC_SUBJECT_TERMS
    ]
    terms = list(dict.fromkeys(terms))
    if len(terms) < 2:
        return []

    cypher = """
    MATCH (tl)
    WHERE (
        any(lbl IN labels(tl) WHERE toLower(lbl) = 'textlabel')
        OR toLower(coalesce(tl.type, '')) IN ['text_label', 'textlabel']
    )
    WITH tl,
         toLower(trim(coalesce(tl.diagram_id, tl.diagramId, tl.image_id, tl.imageId, ''))) AS diagram_id,
         toLower(trim(
            coalesce(tl.value, '') + ' ' +
            coalesce(tl.replacement_text, '') + ' ' +
            coalesce(tl.text, '') + ' ' +
            coalesce(tl.label, '') + ' ' +
            coalesce(tl.name, '')
         )) AS text_blob
    WHERE diagram_id <> '' AND text_blob <> ''
    RETURN diagram_id, text_blob
    """

    try:
        records = neo4j_service.session.run(cypher)
    except Exception:
        return []

    coverage: Dict[str, set] = {}
    for record in records:
        diagram_id_raw = _normalize_label(record.get("diagram_id", ""))
        text_blob = _normalize_label(record.get("text_blob", ""))
        if not diagram_id_raw or not text_blob:
            continue

        matched_terms = coverage.setdefault(diagram_id_raw, set())
        for term in terms:
            if term in text_blob:
                matched_terms.add(term)

    if not coverage:
        return []

    threshold = min(2, len(terms))
    candidate_ids = [
        item[0]
        for item in sorted(coverage.items(), key=lambda kv: len(kv[1]), reverse=True)
        if len(item[1]) >= threshold
    ][: max(1, limit)]

    results: List[Dict[str, Any]] = []
    for raw_id in candidate_ids:
        lookup_ids = [raw_id]
        if not re.search(r"\.(png|jpg|jpeg|webp)$", raw_id):
            lookup_ids.extend([f"{raw_id}.png", f"{raw_id}.jpg", f"{raw_id}.jpeg", f"{raw_id}.webp"])

        matched = None
        for lookup_id in lookup_ids:
            diagram = postgres_service.get_diagram(lookup_id)
            if diagram:
                matched = _serialize_diagram(diagram)
                break

        if matched:
            results.append(matched)

    return results


def _select_best_diagram_by_category_and_subject(
    postgres_service: PostgresService,
    neo4j_service: Neo4jService,
    mongo_service: MongoService,
    category_ids: List[int],
    subject_terms: List[str],
    normalized_query_text: Optional[str] = None,
    category_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    diagrams = _collect_diagrams_from_categories(postgres_service, category_ids, max_diagrams=500)
    if not diagrams:
        return []

    ranked_by_labels = _select_by_neo4j_textlabels(
        neo4j_service,
        diagrams,
        subject_terms,
        normalized_query_text,
        category_name,
    )
    if ranked_by_labels:
        return ranked_by_labels

    if not subject_terms:
        return _first_diagram(diagrams)

    for diagram in diagrams:
        if _diagram_matches_subjects(diagram.get("diagram_id"), subject_terms, mongo_service):
            return [diagram]

    # Strict subject-aware behavior: if a subject was provided but no evidence found
    # in Neo4j TextLabel/Mongo annotation, do not fall back to an unrelated first diagram.
    return []


def _create_video_recommendations(category_name: Optional[str], subject_terms: List[str], query_text: Optional[str]) -> List[Dict[str, Any]]:
    queries = _build_video_search_queries(category_name, subject_terms, query_text)
    return _create_video_recommendations_from_queries(queries)


def _create_video_recommendations_from_queries(queries: List[str]) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []
    for raw_query in queries or []:
        query = _normalize_label(str(raw_query))
        if not query:
            continue
        resolved_watch_url = _resolve_youtube_watch_url_from_query(query)
        priority_score = round(_video_query_priority_score(query), 2)
        recommendations.append(
            {
                "title": f"Video keyword: {query}",
                "keyword": query,
                "priority_score": priority_score,
                "url": resolved_watch_url or f"https://www.youtube.com/results?search_query={quote_plus(query)}",
            }
        )
    return recommendations


def _build_video_search_queries(
    category_name: Optional[str],
    subject_terms: List[str],
    query_text: Optional[str],
    max_queries: int = 6,
) -> List[str]:
    candidates: List[str] = []

    normalized_subjects: List[str] = []
    for raw_term in subject_terms or []:
        normalized_term = _normalize_label(raw_term)
        if not normalized_term:
            continue

        # Keep the full phrase and also meaningful sub-parts so we do not lose
        # intersection hints like "volcanic ash" from mixed labels.
        parts = [normalized_term]
        parts.extend(
            _normalize_label(part)
            for part in re.split(r"\s*(?:,|;|\|| and | & )\s*", normalized_term)
            if _normalize_label(part)
        )

        for part in parts:
            if part in VIDEO_QUERY_STOPWORDS:
                continue
            if len(part) < 2:
                continue
            normalized_subjects.append(part)

    normalized_subjects = list(dict.fromkeys(normalized_subjects))
    normalized_subjects = sorted(normalized_subjects, key=_video_query_priority_score, reverse=True)

    normalized_category = _normalize_label(category_name or "")
    if normalized_category and normalized_category not in VIDEO_QUERY_STOPWORDS:
        candidates.append(normalized_category)

    if normalized_subjects:
        candidates.append(normalized_subjects[0])

    # Include the top informative subject terms and their combination to preserve
    # key intersection context (for example: "cross section f" + "volcano").
    top_subjects = normalized_subjects[:4]
    for subject in top_subjects:
        candidates.append(subject)
    if len(top_subjects) >= 2:
        candidates.append(" ".join(top_subjects[:2]))
    if len(top_subjects) >= 3:
        candidates.append(" ".join(top_subjects[:3]))
    if len(top_subjects) >= 4:
        candidates.append(" ".join(top_subjects[:4]))

    if len(normalized_subjects) >= 2:
        candidates.append(" ".join(normalized_subjects[:2]))
        candidates.append(normalized_subjects[1])

    if normalized_subjects and normalized_category:
        candidates.append(f"{normalized_subjects[0]} {normalized_category}")

    if len(normalized_subjects) >= 2 and normalized_category:
        candidates.append(f"{' '.join(normalized_subjects[:2])} {normalized_category}")

    if top_subjects and normalized_category:
        candidates.append(f"{' '.join(top_subjects)} {normalized_category}")

    normalized_query = _normalize_prompt_to_english(query_text or "") or _normalize_label(query_text or "")
    query_tokens = [
        token
        for token in normalized_query.split()
        if len(token) >= 3 and token not in VIDEO_QUERY_STOPWORDS
    ]
    if query_tokens:
        candidates.append(" ".join(query_tokens[:4]))
    if len(query_tokens) >= 2:
        candidates.append(" ".join(query_tokens[:2]))

    final_queries: List[str] = []
    for candidate in candidates:
        normalized_candidate = _normalize_label(candidate)
        if not normalized_candidate:
            continue
        if normalized_candidate in VIDEO_QUERY_STOPWORDS:
            continue
        if normalized_candidate not in final_queries:
            final_queries.append(normalized_candidate)
        if len(final_queries) >= max_queries:
            break

    if not final_queries:
        final_queries = ["stem science concept"]

    # Keep most meaningful queries first so UI primary video uses better keywords.
    final_queries = sorted(final_queries, key=_video_query_priority_score, reverse=True)
    final_queries = final_queries[:max_queries]

    return final_queries


def _resolve_youtube_watch_url_from_query(query: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", (query or "")).strip()
    if not normalized:
        return None

    search_url = f"https://www.youtube.com/results?search_query={quote_plus(normalized)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code >= 400 or not response.text:
            return None

        match = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', response.text)
        if match:
            return f"https://www.youtube.com/watch?v={match.group(1)}"
    except Exception:
        return None

    return None


def _is_routing_hint_description(text: str) -> bool:
    value = _normalize_label(_strip_accents(text or ""))
    if not value:
        return False

    routing_patterns = [
        "resolved by",
        "required subject intersection",
        "textlabel",
        "category match",
        "matched category",
        "subject intersection",
        "via terms",
        "subject_fallback",
        "routing",
    ]
    return any(pattern in value for pattern in routing_patterns)


def _filter_semantic_descriptions(descriptions: List[str]) -> List[str]:
    clean_items = [str(item).strip() for item in descriptions if isinstance(item, str) and item.strip()]
    semantic_items = [item for item in clean_items if not _is_routing_hint_description(item)]
    return semantic_items


def _detect_explanation_language(
    query_text: Optional[str],
    descriptions: List[str],
    subject_terms: List[str],
) -> str:
    primary_text = (query_text or "").strip()
    fallback_text = " ".join(descriptions[:3] + subject_terms[:5]).strip()
    source = primary_text or fallback_text
    if not source:
        return "en"

    lowered = source.lower()
    ascii_only = _strip_accents(lowered)

    # Explicit Vietnamese markers (with diacritics)
    if re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", lowered):
        return "vi"

    # Vietnamese stopword heuristic (works even without accents)
    vi_markers = {
        "tai", "sao", "nhu", "the", "nao", "vi", "du", "cho", "toi", "biet", "hay",
        "vong", "tuan", "hoan", "nuoc", "tho", "cao", "co", "la", "gi", "khong", "voi",
        "cac", "quy", "trinh", "dien", "ra", "phan", "tich", "giai", "thich",
        "qua", "trinh", "quang", "hop", "thuc", "vat",
    }
    tokens = re.findall(r"\b[a-zA-Z]+\b", ascii_only)
    vi_hits = sum(1 for token in tokens if token in vi_markers)
    if vi_hits >= 2:
        return "vi"

    return "en"


def _detect_stem_topic(
    category_name: Optional[str],
    subject_terms: List[str],
    query_text: Optional[str],
    descriptions: List[str],
) -> Dict[str, str]:
    text_blob = " ".join(
        [category_name or "", query_text or "", " ".join(subject_terms), " ".join(descriptions)]
    )
    normalized = _normalize_label(_strip_accents(text_blob))

    if any(
        keyword in normalized
        for keyword in [
            "food chain",
            "chuoi thuc an",
            "predator",
            "prey",
            "rabbit",
            "fox",
            "grass",
            "cao an",
            "tho an",
            "an co",
        ]
    ):
        return {
            "key": "food_chain",
            "focus": "food chain",
        }

    if any(keyword in normalized for keyword in ["water cycle", "vong tuan hoan nuoc", "evaporation", "condensation"]):
        return {
            "key": "water_cycle",
            "focus": "water cycle",
        }

    if any(keyword in normalized for keyword in ["life cycle", "vong doi", "metamorphosis"]):
        return {
            "key": "life_cycle",
            "focus": "life cycle",
        }

    if any(
        keyword in normalized
        for keyword in [
            "photosynthesis",
            "quang hop",
            "chlorophyll",
            "co2",
            "carbon dioxide",
            "sunlight",
            "glucose",
        ]
    ):
        return {
            "key": "photosynthesis",
            "focus": "photosynthesis",
        }

    fallback_focus = subject_terms[0] if subject_terms else (category_name or "chủ đề STEM")
    return {
        "key": "generic",
        "focus": fallback_focus,
    }


def _extract_food_chain_roles(
    subject_terms: List[str],
    query_text: Optional[str],
    descriptions: List[str],
) -> Dict[str, str]:
    source = _normalize_label(_strip_accents(" ".join([" ".join(subject_terms), query_text or "", " ".join(descriptions)])))

    producer = "cỏ/thực vật"
    herbivore = "động vật ăn cỏ"
    predator = "động vật ăn thịt"

    if any(token in source for token in ["grass", "co", "plant", "thuc vat", "leaf", "la cay"]):
        producer = "cỏ/thực vật"
    if any(token in source for token in ["rabbit", "tho", "deer", "nai", "goat", "cow", "bo"]):
        herbivore = "thỏ (động vật ăn cỏ)"
    if any(token in source for token in ["fox", "cao", "wolf", "soi", "tiger", "ho", "eagle", "dai bang"]):
        predator = "cáo (động vật săn mồi)"

    return {
        "producer": producer,
        "herbivore": herbivore,
        "predator": predator,
    }


def _topic_title_by_language(topic_key: str, focus: str, language: str) -> str:
    if topic_key == "food_chain":
        return "Chuỗi thức ăn và quan hệ dinh dưỡng" if language == "vi" else "Food chain and trophic relationships"
    if topic_key == "water_cycle":
        return "Vòng tuần hoàn nước" if language == "vi" else "Water cycle"
    if topic_key == "life_cycle":
        return "Vòng đời sinh học" if language == "vi" else "Biological life cycle"
    if topic_key == "photosynthesis":
        return "Quá trình quang hợp" if language == "vi" else "Photosynthesis process"
    return (f"Chủ đề STEM: {focus}" if language == "vi" else f"STEM topic: {focus}")


def _build_diagram_explanation(
    category_name: Optional[str],
    subject_terms: List[str],
    query_text: Optional[str],
    descriptions: List[str],
    scientific_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    semantic_descriptions = _filter_semantic_descriptions(descriptions)
    topic = _detect_stem_topic(category_name, subject_terms, query_text, semantic_descriptions)
    focus = topic.get("focus") or (subject_terms[0] if subject_terms else (category_name or "chủ đề STEM"))
    topic_key = topic.get("key")
    language = _detect_explanation_language(query_text, semantic_descriptions, subject_terms)
    topic_title = _topic_title_by_language(topic_key or "generic", focus, language)

    summary = str(scientific_analysis.get("summary") or "").strip()
    if not summary and semantic_descriptions:
        summary = semantic_descriptions[0]

    if not summary and topic_key == "food_chain":
        roles = _extract_food_chain_roles(subject_terms, query_text, semantic_descriptions)
        if language == "vi":
            summary = (
                f"Diagram mô tả chuỗi thức ăn, trong đó {roles['producer']} là bậc sản xuất, "
                f"{roles['herbivore']} tiêu thụ thực vật và {roles['predator']} tiêu thụ bậc thấp hơn. "
                "Vì vậy thỏ ăn cỏ nhưng không ăn cáo do khác biệt sinh học về cấu tạo răng-hệ tiêu hóa "
                "và vị trí dinh dưỡng trong lưới thức ăn."
            )
        else:
            summary = (
                f"This diagram describes a food chain where {roles['producer']} acts as the producer level, "
                f"{roles['herbivore']} consumes plants, and {roles['predator']} feeds on lower trophic levels. "
                "A rabbit eats grass but does not eat a fox because of biological constraints in dentition, "
                "digestive adaptation, and trophic position."
            )

    if not summary and topic_key == "photosynthesis":
        if language == "vi":
            summary = (
                "Quang hợp là quá trình thực vật sử dụng năng lượng ánh sáng để chuyển CO₂ và nước thành glucose, "
                "đồng thời giải phóng O₂. Diagram giúp thấy rõ nơi diễn ra (lục lạp), điều kiện đầu vào và sản phẩm đầu ra."
            )
        else:
            summary = (
                "Photosynthesis is the process in which plants use light energy to convert CO2 and water into glucose, "
                "while releasing O2. The diagram clarifies reaction location (chloroplast), required inputs, and outputs."
            )

    if not summary:
        if language == "vi":
            summary = (
                f"Diagram này biểu diễn '{focus}' theo cấu trúc hệ thống, làm rõ cơ chế tương tác giữa "
                "các thành phần, điều kiện vận hành và hệ quả ở từng giai đoạn của tiến trình khoa học."
            )
        else:
            summary = (
                f"This diagram represents '{focus}' as a system-level model, clarifying component interactions, "
                "operating conditions, and stage-wise scientific outcomes."
            )

    reasoning_steps = [
        str(step).strip()
        for step in (scientific_analysis.get("reasoning_steps") or [])
        if str(step).strip()
    ]
    if not reasoning_steps and semantic_descriptions:
        reasoning_steps = semantic_descriptions[:4]

    if not reasoning_steps and topic_key == "food_chain":
        roles = _extract_food_chain_roles(subject_terms, query_text, semantic_descriptions)
        if language == "vi":
            reasoning_steps = [
                f"Xác định bậc dinh dưỡng: {roles['producer']} thuộc nhóm sinh vật sản xuất tạo sinh khối ban đầu.",
                f"{roles['herbivore']} thuộc nhóm tiêu thụ bậc 1, nhận năng lượng trực tiếp từ thực vật.",
                f"{roles['predator']} thuộc nhóm tiêu thụ bậc cao hơn, săn mồi để nhận năng lượng từ động vật khác.",
                "Giải thích quan hệ 'thỏ không ăn cáo': khác biệt cấu tạo cơ thể, tập tính kiếm ăn và vai trò sinh thái khiến chiều năng lượng không đảo ngược.",
            ]
        else:
            reasoning_steps = [
                f"Identify trophic levels: {roles['producer']} functions as the producer level that generates primary biomass.",
                f"{roles['herbivore']} is a primary consumer receiving energy directly from plants.",
                f"{roles['predator']} is a higher-level consumer obtaining energy by predation.",
                "Explain why a rabbit does not eat a fox: morphology, feeding behavior, and ecological role constrain energy flow direction.",
            ]

    if not reasoning_steps and topic_key == "photosynthesis":
        if language == "vi":
            reasoning_steps = [
                "Xác định đầu vào của quang hợp: ánh sáng, CO₂ và nước; vị trí chủ yếu là lục lạp trong tế bào lá.",
                "Pha sáng hấp thụ photon để tạo ATP/NADPH và giải phóng O₂ từ quá trình quang phân ly nước.",
                "Pha tối (chu trình Calvin) cố định CO₂ để tổng hợp hợp chất hữu cơ, cuối cùng tạo glucose.",
                "Giải thích các yếu tố ảnh hưởng (cường độ sáng, nồng độ CO₂, nhiệt độ) làm tăng/giảm tốc độ quang hợp.",
            ]
        else:
            reasoning_steps = [
                "Identify photosynthesis inputs: light, CO2, and water; the main site is the chloroplast in leaf cells.",
                "Light-dependent reactions capture photons to generate ATP/NADPH and release O2 via water splitting.",
                "The Calvin cycle fixes CO2 into organic compounds and ultimately produces glucose.",
                "Explain controlling factors (light intensity, CO2 concentration, temperature) that modulate photosynthetic rate.",
            ]

    if not reasoning_steps:
        if language == "vi":
            reasoning_steps = [
                f"Xác định các thực thể trung tâm trong hệ '{focus}' và vai trò chức năng của từng thực thể.",
                "Phân tích hướng dịch chuyển năng lượng/vật chất/thông tin giữa các nút theo đúng chiều nhân quả.",
                "Làm rõ điều kiện kích hoạt, biến đổi trung gian và trạng thái cân bằng hoặc đầu ra cuối cùng.",
                "Đối chiếu các vòng phản hồi (feedback) và tác động của biến thiên môi trường lên toàn hệ thống.",
            ]
        else:
            reasoning_steps = [
                f"Identify the core entities in '{focus}' and define each functional role.",
                "Track energy/material/information flow across nodes with correct causal direction.",
                "Clarify triggering conditions, intermediate transformations, and terminal states.",
                "Examine feedback loops and the effect of environmental variation on system behavior.",
            ]

    key_points = [
        str(point).strip()
        for point in (scientific_analysis.get("key_points") or [])
        if str(point).strip()
    ]
    if not key_points and topic_key == "food_chain":
        if language == "vi":
            key_points = [
                "Chuỗi thức ăn thể hiện dòng năng lượng một chiều từ sinh vật sản xuất đến các bậc tiêu thụ.",
                "Quan hệ ăn - bị ăn phụ thuộc vào thích nghi sinh học và vị trí dinh dưỡng của từng loài.",
                "Động vật ăn cỏ không trở thành loài săn mồi đỉnh do giới hạn sinh lý và hành vi kiếm ăn.",
            ]
        else:
            key_points = [
                "A food chain models one-way energy transfer from producers to consumers.",
                "Predator-prey interactions are constrained by biological adaptation and trophic position.",
                "Herbivores do not become apex predators because of physiological and behavioral limits.",
            ]
    if not key_points and topic_key == "photosynthesis":
        if language == "vi":
            key_points = [
                "Quang hợp là cơ chế chuyển năng lượng ánh sáng thành năng lượng hóa học tích lũy trong glucose.",
                "CO₂ và nước là nguyên liệu chính, O₂ là sản phẩm phụ quan trọng cho hô hấp của sinh vật hiếu khí.",
                "Tốc độ quang hợp phụ thuộc mạnh vào ánh sáng, CO₂, nhiệt độ và tình trạng sinh lý của lá.",
            ]
        else:
            key_points = [
                "Photosynthesis converts light energy into chemical energy stored in glucose.",
                "CO2 and water are primary reactants, while O2 is a crucial byproduct for aerobic life.",
                "Photosynthetic rate is strongly regulated by light, CO2, temperature, and leaf physiology.",
            ]
    if not key_points:
        if language == "vi":
            key_points = [
                f"Trọng tâm mô hình là cơ chế vận hành của '{focus}' chứ không chỉ mô tả hiện tượng bề mặt.",
                "Mỗi bước phản ánh một mắt xích nhân quả có thể kiểm chứng bằng quan sát/thực nghiệm.",
                "Hiểu đúng thứ tự tiến trình giúp phân biệt yếu tố nguyên nhân, điều kiện và kết quả.",
            ]
        else:
            key_points = [
                f"The model focuses on the mechanism of '{focus}', not only surface-level phenomena.",
                "Each stage encodes a causal link that can be validated through observation or experiment.",
                "Correct sequence interpretation helps separate causes, conditions, and outcomes.",
            ]

    applications = [
        str(item).strip()
        for item in (scientific_analysis.get("applications") or [])
        if str(item).strip()
    ]
    if not applications and topic_key == "food_chain":
        if language == "vi":
            applications = [
                "Phân tích tác động khi một mắt xích trong hệ sinh thái suy giảm hoặc biến mất.",
                "Giải thích hiện tượng mất cân bằng sinh thái khi số lượng loài săn mồi/con mồi thay đổi mạnh.",
                "Ứng dụng trong giáo dục môi trường và bảo tồn đa dạng sinh học địa phương.",
            ]
        else:
            applications = [
                "Assess ecosystem impact when a trophic link declines or disappears.",
                "Explain ecological imbalance when predator-prey population ratios shift rapidly.",
                "Apply in environmental education and local biodiversity conservation planning.",
            ]
    if not applications and topic_key == "photosynthesis":
        if language == "vi":
            applications = [
                "Giải thích vì sao điều kiện nhà kính (ánh sáng/CO₂/nhiệt độ) ảnh hưởng trực tiếp đến năng suất cây trồng.",
                "Ứng dụng trong tối ưu hóa chăm sóc cây: tưới, thông gió, bố trí ánh sáng và mật độ trồng.",
                "Làm nền tảng để học sâu hơn về chu trình carbon và biến đổi khí hậu.",
            ]
        else:
            applications = [
                "Explain how greenhouse conditions (light/CO2/temperature) directly affect crop productivity.",
                "Apply to plant-care optimization: irrigation, ventilation, light layout, and planting density.",
                "Use as a foundation for deeper learning on the carbon cycle and climate change.",
            ]
    if not applications:
        if language == "vi":
            applications = [
                "Phân tích hiện tượng tự nhiên và dự đoán xu hướng thay đổi của hệ trong bối cảnh thực tế.",
                "Thiết kế hoạt động học theo năng lực giải quyết vấn đề và tư duy hệ thống.",
                "Làm khung tham chiếu để so sánh nhiều mô hình khoa học có cơ chế tương đồng.",
            ]
        else:
            applications = [
                "Analyze natural phenomena and predict system-level trends in real contexts.",
                "Design learning activities that develop problem-solving and systems thinking.",
                "Use as a reference frame for comparing mechanisms across scientific models.",
            ]

    glossary = [
        item
        for item in (scientific_analysis.get("glossary") or [])
        if isinstance(item, dict) and (item.get("term") or item.get("definition"))
    ]

    return {
        "title": (f"Phân tích chuyên sâu: {topic_title}" if language == "vi" else f"Advanced analysis: {topic_title}"),
        "explanation_level": "advanced",
        "language": language,
        "topic_key": topic_key or "generic",
        "overview": summary,
        "process_steps": reasoning_steps,
        "key_takeaways": key_points,
        "applications": applications,
        "glossary": glossary,
        "learning_prompt": (
            (
                f"Hãy tái lập luận cơ chế của '{topic_title}' theo chuỗi nhân quả, chỉ ra biến số chi phối "
                "và nêu một tình huống thực tế có thể kiểm chứng mô hình này."
            )
            if language == "vi"
            else (
                f"Reconstruct the mechanism of '{topic_title}' as a causal chain, identify controlling variables, "
                "and propose one real-world scenario to validate the model."
            )
        ),
        "source_query": (query_text or "").strip() or None,
    }


def _extract_json_from_text(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _generate_explanation_with_gemini(
    query_text: Optional[str],
    base_explanation: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    gemini_keys = list(getattr(config, "GEMINI_API_KEYS", []) or [])
    if not gemini_keys and getattr(config, "GEMINI_API_KEY", ""):
        gemini_keys = [str(config.GEMINI_API_KEY).strip()]

    gemini_keys = [key for key in gemini_keys if key]
    if not gemini_keys:
        return None

    language = base_explanation.get("language") or "en"
    language_label = "Vietnamese" if language == "vi" else "English"
    topic_title = base_explanation.get("title") or "STEM topic"
    topic_key = base_explanation.get("topic_key") or "generic"

    prompt = (
        "You are a STEM tutor. Generate a precise explanation for one STEM diagram. "
        f"Write in {language_label}. Keep it curriculum-friendly and scientifically accurate.\n\n"
        f"User query: {query_text or ''}\n"
        f"Topic key: {topic_key}\n"
        f"Topic title: {topic_title}\n"
        f"Fallback overview: {base_explanation.get('overview') or ''}\n\n"
        "Return ONLY valid JSON object with fields: "
        "title (string), overview (string), process_steps (string[]), key_takeaways (string[]), "
        "applications (string[]), learning_prompt (string)."
    )

    model_candidates = [
        str(getattr(config, "GEMINI_MODEL", "") or "").strip(),
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash-001",
        "gemini-2.0-flash-lite",
    ]
    model_candidates = [model for model in dict.fromkeys(model_candidates) if model]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "topP": 0.9,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
        },
    }

    for model_name in model_candidates:
        endpoint = f"{config.GEMINI_API_BASE}/models/{model_name}:generateContent"

        for key in gemini_keys:
            try:
                response = requests.post(
                    endpoint,
                    params={"key": key},
                    json=payload,
                    timeout=20,
                )
                if response.status_code in {401, 403, 429}:
                    continue
                if response.status_code == 404:
                    break

                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    continue

                parts = ((candidates[0].get("content") or {}).get("parts") or [])
                if not parts:
                    continue

                text = "\n".join([str(part.get("text") or "") for part in parts if isinstance(part, dict)])
                parsed = _extract_json_from_text(text)
                if not parsed:
                    continue

                result: Dict[str, Any] = {
                    "title": str(parsed.get("title") or base_explanation.get("title") or "").strip(),
                    "overview": str(parsed.get("overview") or base_explanation.get("overview") or "").strip(),
                    "process_steps": [
                        str(item).strip() for item in (parsed.get("process_steps") or []) if str(item).strip()
                    ],
                    "key_takeaways": [
                        str(item).strip() for item in (parsed.get("key_takeaways") or []) if str(item).strip()
                    ],
                    "applications": [
                        str(item).strip() for item in (parsed.get("applications") or []) if str(item).strip()
                    ],
                    "learning_prompt": str(parsed.get("learning_prompt") or "").strip(),
                }

                if not result["overview"]:
                    continue

                return result
            except Exception:
                continue

    return None


def _resolve_and_cache_diagram_explanation(
    final_output: Optional[Dict[str, Any]],
    mongo_service: MongoService,
    query_text: Optional[str],
    normalized_query_text: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not final_output:
        return final_output

    diagram = final_output.get("diagram") or {}
    diagram_id = diagram.get("diagram_id")
    if not diagram_id:
        return final_output

    explanation = dict(final_output.get("diagram_explanation") or {})
    language = explanation.get("language") or "en"
    topic_key = explanation.get("topic_key") or "generic"

    cached = mongo_service.get_diagram_explanation(diagram_id=diagram_id, language=language, topic_key=topic_key)
    if cached and isinstance(cached.get("explanation"), dict):
        cached_explanation = dict(cached.get("explanation") or {})
        cached_explanation["language"] = cached_explanation.get("language") or language
        cached_explanation["topic_key"] = cached_explanation.get("topic_key") or topic_key
        cached_explanation["source"] = "cache"
        final_output["diagram_explanation"] = cached_explanation
        return final_output

    ai_explanation = _generate_explanation_with_gemini(
        query_text=query_text or normalized_query_text,
        base_explanation=explanation,
    )

    if ai_explanation:
        merged_explanation = {
            **explanation,
            **ai_explanation,
            "language": language,
            "topic_key": topic_key,
            "source": "gemini",
            "source_query": (query_text or normalized_query_text or "").strip() or None,
        }
        final_output["diagram_explanation"] = merged_explanation
        mongo_service.upsert_diagram_explanation(
            diagram_id=diagram_id,
            language=language,
            topic_key=topic_key,
            explanation=merged_explanation,
            source_query=query_text or normalized_query_text,
            generator="gemini",
        )
        return final_output

    explanation["source"] = explanation.get("source") or "template"
    final_output["diagram_explanation"] = explanation
    mongo_service.upsert_diagram_explanation(
        diagram_id=diagram_id,
        language=language,
        topic_key=topic_key,
        explanation=explanation,
        source_query=query_text or normalized_query_text,
        generator="template",
    )
    return final_output


def _build_final_output(
    matched_diagrams: List[Dict[str, Any]],
    descriptions: List[str],
    category_name: Optional[str],
    subject_terms: List[str],
    query_text: Optional[str],
    model_output: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base_description = " ".join([desc for desc in descriptions if desc]).strip()
    if not base_description:
        focus = subject_terms[0] if subject_terms else (category_name or "the requested STEM concept")
        base_description = f"This STEM diagram explains {focus} with visual relationships for easier learning."

    creative_output = (model_output or {}).get("creative_recommendation") or {}
    creative_description = creative_output.get("description")
    if isinstance(creative_description, str) and creative_description.strip():
        base_description = creative_description.strip()

    creative_queries = [
        _normalize_label(str(query))
        for query in (creative_output.get("youtube_queries") or [])
        if _normalize_label(str(query))
    ]
    fallback_queries = _build_video_search_queries(category_name, subject_terms, query_text)

    merged_queries: List[str] = []
    for query in fallback_queries + creative_queries:
        normalized_query = _normalize_label(query)
        if not normalized_query:
            continue
        if normalized_query not in merged_queries:
            merged_queries.append(normalized_query)
        if len(merged_queries) >= 6:
            break

    video_recommendations = _create_video_recommendations_from_queries(merged_queries)
    scientific_analysis = creative_output.get("scientific_analysis") or {}
    diagram_explanation = _build_diagram_explanation(
        category_name=category_name,
        subject_terms=subject_terms,
        query_text=query_text,
        descriptions=descriptions,
        scientific_analysis=scientific_analysis,
    )

    return {
        "diagram": matched_diagrams[0] if matched_diagrams else None,
        "description": base_description,
        "video_recommendations": video_recommendations,
        "scientific_analysis": scientific_analysis,
        "diagram_explanation": diagram_explanation,
    }


def _derive_subject_terms_from_text(normalized_en_text: str) -> List[str]:
    if not normalized_en_text:
        return []
    tokens = [
        token for token in _normalize_label(normalized_en_text).split()
        if token and token not in EN_FILLER_WORDS and token not in GENERIC_SUBJECT_TERMS and len(token) >= 3
    ]
    return list(dict.fromkeys(tokens))


def _extract_query_phrases(normalized_en_text: str, max_n: int = 4) -> List[str]:
    tokens = [
        token
        for token in _normalize_label(normalized_en_text).split()
        if token and token not in EN_FILLER_WORDS
    ]
    if not tokens:
        return []

    phrases: List[str] = []
    upper = min(max_n, len(tokens))
    for size in range(2, upper + 1):
        for i in range(len(tokens) - size + 1):
            phrase_tokens = tokens[i:i + size]
            if all(token in GENERIC_SUBJECT_TERMS for token in phrase_tokens):
                continue
            phrase = " ".join(phrase_tokens)
            if len(phrase) >= 8:
                phrases.append(phrase)

    return list(dict.fromkeys(phrases))


def _extract_core_subject_terms(subject_terms: List[str], normalized_query_text: Optional[str]) -> List[str]:
    candidate_terms = _safe_terms(subject_terms)
    candidate_terms.extend(_derive_subject_terms_from_text(normalized_query_text or ""))

    core_terms: List[str] = []
    for term in list(dict.fromkeys(candidate_terms)):
        normalized_term = _normalize_label(term)
        if not normalized_term:
            continue
        if normalized_term in GENERIC_SUBJECT_TERMS:
            continue
        if normalized_term in EN_FILLER_WORDS:
            continue
        if len(normalized_term) < 4:
            continue
        core_terms.append(normalized_term)

    return list(dict.fromkeys(core_terms))


def _slugify_identifier(value: str, fallback: str = "autolearned") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return cleaned[:50] if cleaned else fallback


def _find_category_by_name(postgres_service: PostgresService, category_name: str) -> Optional[Any]:
    target = _normalize_label(category_name)
    if not target:
        return None
    categories = postgres_service.get_all_categories(skip=0, limit=10000)
    for category in categories:
        if _normalize_label(category.name) == target:
            return category
    return None


def _find_root_subject_by_name(postgres_service: PostgresService, root_subject_name: str) -> Optional[Any]:
    target = _normalize_label(root_subject_name)
    if not target:
        return None
    roots = postgres_service.get_all_root_subjects(skip=0, limit=10000)
    for root_subject in roots:
        if _normalize_label(root_subject.name) == target:
            return root_subject
    return None


def _find_subject_exact(postgres_service: PostgresService, subject_name: str) -> Optional[Any]:
    target = _normalize_label(subject_name)
    if not target:
        return None
    candidates = postgres_service.search_subjects(name=subject_name)
    for subject in candidates:
        if _normalize_label(subject.name) == target:
            return subject
    return None


def _collect_subject_names_from_pending(pending_item: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    model_output = pending_item.get("model_output") or {}

    for candidate in model_output.get("subject_candidates", []) or []:
        name = candidate.get("subject_name") if isinstance(candidate, dict) else None
        if name:
            result.append(str(name))

    for label in model_output.get("detected_labels", []) or []:
        if label:
            result.append(str(label))

    for triple in model_output.get("sro_candidates", []) or []:
        if isinstance(triple, dict):
            if triple.get("subject"):
                result.append(str(triple.get("subject")))
            if triple.get("object"):
                result.append(str(triple.get("object")))

    for triple in pending_item.get("triples", []) or []:
        if isinstance(triple, dict):
            if triple.get("subject"):
                result.append(str(triple.get("subject")))
            if triple.get("object"):
                result.append(str(triple.get("object")))

    normalized = [_normalize_label(item) for item in result if item and _normalize_label(item)]
    return list(dict.fromkeys(normalized))


def _collect_relationship_from_pending(pending_item: Dict[str, Any]) -> str:
    model_output = pending_item.get("model_output") or {}
    for triple in model_output.get("sro_candidates", []) or []:
        if isinstance(triple, dict) and triple.get("relationship"):
            return _normalize_label(str(triple.get("relationship")))

    for triple in pending_item.get("triples", []) or []:
        if isinstance(triple, dict) and triple.get("relationship"):
            return _normalize_label(str(triple.get("relationship")))

    return "related_to"


class PendingLearningApprovalRequest(BaseModel):
    approved_by: Optional[str] = None
    category_name: Optional[str] = None
    root_subject_name: Optional[str] = None
    relationship_name: Optional[str] = None
    subject_names: Optional[List[str]] = None
    note: Optional[str] = None


class PendingLearningRejectRequest(BaseModel):
    rejected_by: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None


def _parse_triple_from_text(text: str) -> Optional[Dict[str, str]]:
    if not text:
        return None

    # Restrict explicit triple syntax to avoid mis-parsing natural long sentences.
    parts = re.split(r"\s*(?:->|=>|\||;)\s*", text)
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
        postgres_diagrams = [_serialize_diagram(d) for d in diagrams]

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
            neo4j_diagrams.append(_serialize_diagram(diagram))

    merged_diagrams = list({d["diagram_id"]: d for d in (postgres_diagrams + neo4j_diagrams)}.values())
    one_diagram = _first_diagram(merged_diagrams)

    return {
        "postgres": {
            "categories": postgres_results,
            "diagrams": _first_diagram(postgres_diagrams)
        },
        "neo4j": neo4j_results,
        "mongo": mongo_annotations,
        "descriptions": list(dict.fromkeys(descriptions)),
        "diagrams": one_diagram
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
    analysis_mode: Optional[str] = Form(None),
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
    normalized_query_text: Optional[str] = None
    routing_mode: Optional[str] = None
    pending_learning_item: Optional[Dict[str, Any]] = None
    final_output: Optional[Dict[str, Any]] = None
    phase: Optional[str] = None
    analysis_case: Optional[str] = None
    selected_analysis_mode = _normalize_analysis_mode(analysis_mode)
    request_started_at = time.perf_counter()
    model_analysis_ms: Optional[float] = None
    kg_query_ms: Optional[float] = None

    try:
        model_files = None
        model_data: Dict[str, Any] = {}

        if query_text:
            model_data["query_text"] = query_text
        model_data["analysis_mode"] = selected_analysis_mode

        if image:
            os.makedirs(config.UPLOAD_DIR, exist_ok=True)
            extension = os.path.splitext(image.filename or "")[1] or ".png"
            filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}{extension}"
            saved_image_path = os.path.join(config.UPLOAD_DIR, filename)
            saved_image_url = f"/images/uploads/{filename}"

            image_bytes = image.file.read()
            with open(saved_image_path, "wb") as f:
                f.write(image_bytes)
            model_files = {
                "image": (image.filename, image_bytes, image.content_type or "application/octet-stream")
            }

        model_stage_started_at = time.perf_counter()
        try:
            response = requests.post(
                config.MODEL_OCR_URL,
                data=model_data,
                files=model_files,
                timeout=75
            )
            if not response.ok:
                response_detail = response.text
                try:
                    response_json = response.json()
                    if isinstance(response_json, dict):
                        response_detail = response_json.get("error") or response_json.get("message") or response_detail
                except Exception:
                    pass
                raise HTTPException(
                    status_code=502,
                    detail=f"Model analyze error ({response.status_code}): {response_detail}",
                )
            model_output = response.json()
            model_analysis_ms = round((time.perf_counter() - model_stage_started_at) * 1000.0, 3)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=502, detail=f"Model analyze error: {str(e)}")

        kg_stage_started_at = time.perf_counter()

        phase = model_output.get("phase") if model_output else None
        analysis_case = model_output.get("analysis_case") if model_output else None
        normalized_query_text = (
            model_output.get("corrected_query_en")
            or model_output.get("normalized_query_en")
            or (_normalize_prompt_to_english(query_text) if query_text else None)
        )

        objects = model_output.get("objects", []) if model_output else []
        labels = [
            obj.get("translated_text") or obj.get("original_text") or ""
            for obj in objects
        ]
        triples.extend(_build_triples_from_labels(labels))

        for inferred_triple in model_output.get("sro_candidates", []) if model_output else []:
            if inferred_triple.get("subject") and inferred_triple.get("relationship") and inferred_triple.get("object"):
                relation_value = _normalize_label(inferred_triple.get("relationship"))
                if relation_value.startswith("not_"):
                    continue
                triples.append(
                    {
                        "subject": _normalize_label(inferred_triple.get("subject")),
                        "relationship": relation_value,
                        "object": _normalize_label(inferred_triple.get("object")),
                    }
                )

        if query_text:
            triple_from_text = _parse_triple_from_text(query_text)
            if triple_from_text:
                triples.insert(0, triple_from_text)

        triples = [dict(item) for item in {tuple(t.items()) for t in triples if t.get("subject") and t.get("relationship") and t.get("object")}]
        triple_focus_terms = _derive_focus_subject_terms_from_triples(triples)

        query_results: List[Dict[str, Any]] = []

        model_category_candidates = model_output.get("category_candidates", []) if model_output else []
        model_subject_candidates = model_output.get("subject_candidates", []) if model_output else []
        subject_terms = _safe_terms(
            [item.get("subject_name", "") for item in model_subject_candidates]
            + labels
            + _derive_subject_terms_from_text(normalized_query_text or "")
        )
        core_subject_terms = _extract_core_subject_terms(subject_terms, normalized_query_text)

        if len(core_subject_terms) >= 2:
            strict_core_diagrams = _search_diagram_by_required_subject_terms(
                neo4j_service,
                postgres_service,
                required_terms=core_subject_terms,
                limit=3,
            )
            if strict_core_diagrams:
                routing_mode = "subject_intersection_priority"
                descriptions = [
                    f"Resolved by required subject intersection in TextLabels: {', '.join(core_subject_terms[:4])}"
                ]
                query_results = [
                    {
                        "triple": {
                            "subject": " and ".join(core_subject_terms[:2]),
                            "relationship": "subject_intersection",
                            "object": strict_core_diagrams[0].get("diagram_id"),
                        },
                        "results": {
                            "postgres": {
                                "categories": [],
                                "diagrams": _first_diagram(strict_core_diagrams),
                            },
                            "neo4j": [],
                            "mongo": [],
                            "descriptions": descriptions,
                            "diagrams": _first_diagram(strict_core_diagrams),
                        },
                    }
                ]
                final_output = _build_final_output(
                    _first_diagram(strict_core_diagrams),
                    descriptions,
                    None,
                    core_subject_terms,
                    query_text or normalized_query_text,
                    model_output=model_output,
                )

        if model_category_candidates:
            routing_mode = "category_shortcut"
            top_category = model_category_candidates[0]
            category_ids = [item.get("category_id") for item in model_category_candidates if item.get("category_id") is not None]
            matched_diagrams = _select_best_diagram_by_category_and_subject(
                postgres_service,
                neo4j_service,
                mongo_service,
                category_ids,
                subject_terms,
                normalized_query_text=normalized_query_text,
                category_name=top_category.get("category_name"),
            )
            if subject_terms and not matched_diagrams:
                # Keep searching via other routing paths instead of returning unrelated category diagram.
                model_category_candidates = []

        if model_category_candidates:
            top_category = model_category_candidates[0]
            category_ids = [item.get("category_id") for item in model_category_candidates if item.get("category_id") is not None]
            matched_diagrams = _select_best_diagram_by_category_and_subject(
                postgres_service,
                neo4j_service,
                mongo_service,
                category_ids,
                subject_terms,
                normalized_query_text=normalized_query_text,
                category_name=top_category.get("category_name"),
            )
            descriptions = [
                f"Category match: {item.get('category_name')} (root: {item.get('root_category')}) via terms {', '.join(item.get('matched_terms', []))}"
                for item in model_category_candidates
            ]
            query_results = [
                {
                    "triple": {
                        "subject": normalized_query_text or (query_text or "input"),
                        "relationship": "category_match",
                        "object": top_category.get("category_name"),
                    },
                    "results": {
                        "postgres": {
                            "categories": model_category_candidates,
                            "diagrams": matched_diagrams,
                        },
                        "neo4j": [],
                        "mongo": [],
                        "descriptions": descriptions,
                        "diagrams": matched_diagrams,
                    },
                }
            ]
            final_output = _build_final_output(
                matched_diagrams,
                descriptions,
                top_category.get("category_name"),
                subject_terms,
                query_text or normalized_query_text,
                model_output=model_output,
            )

        if not query_results and normalized_query_text:
            keyword_candidates = _extract_keyword_candidates(normalized_query_text)
            category_matches = postgres_service.search_categories_by_keywords(keyword_candidates, limit=5)

            if category_matches:
                routing_mode = "category_shortcut"
                category_ids = [item.get("category_id") for item in category_matches if item.get("category_id") is not None]
                matched_diagrams = _select_best_diagram_by_category_and_subject(
                    postgres_service,
                    neo4j_service,
                    mongo_service,
                    category_ids,
                    subject_terms,
                    normalized_query_text=normalized_query_text,
                    category_name=category_matches[0]["category_name"],
                )

                if subject_terms and not matched_diagrams:
                    category_matches = []

            if category_matches:
                descriptions = [
                    f"Matched category '{item['category_name']}' from keyword(s): {', '.join(item['matched_keywords'])}"
                    for item in category_matches
                ]

                query_results = [
                    {
                        "triple": {
                            "subject": normalized_query_text,
                            "relationship": "category_match",
                            "object": category_matches[0]["category_name"],
                        },
                        "results": {
                            "postgres": {
                                "categories": category_matches,
                                "diagrams": matched_diagrams,
                            },
                            "neo4j": [],
                            "mongo": [],
                            "descriptions": descriptions,
                            "diagrams": matched_diagrams,
                        },
                    }
                ]

                final_output = _build_final_output(
                    matched_diagrams,
                    descriptions,
                    category_matches[0]["category_name"],
                    subject_terms,
                    query_text or normalized_query_text,
                    model_output=model_output,
                )

        if not query_results and len(triple_focus_terms) >= 2:
            strict_diagrams = _search_diagram_by_required_subject_terms(
                neo4j_service,
                postgres_service,
                required_terms=triple_focus_terms,
                limit=3,
            )
            if strict_diagrams:
                routing_mode = "triple_subject_textlabel"
                descriptions = [
                    f"Resolved diagram by required TextLabel intersection: {', '.join(triple_focus_terms)}"
                ]
                query_results = [
                    {
                        "triple": {
                            "subject": " and ".join(triple_focus_terms[:2]),
                            "relationship": "textlabel_intersection",
                            "object": strict_diagrams[0].get("diagram_id"),
                        },
                        "results": {
                            "postgres": {
                                "categories": [],
                                "diagrams": _first_diagram(strict_diagrams),
                            },
                            "neo4j": [],
                            "mongo": [],
                            "descriptions": descriptions,
                            "diagrams": _first_diagram(strict_diagrams),
                        },
                    }
                ]
                final_output = _build_final_output(
                    _first_diagram(strict_diagrams),
                    descriptions,
                    None,
                    triple_focus_terms,
                    query_text or normalized_query_text,
                    model_output=model_output,
                )

        if not query_results and triples:
            routing_mode = "triple"
            triple_results = [
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

            intersection_diagrams: List[Dict[str, Any]] = []
            if len(triple_results) >= 2:
                diagram_sets: List[set] = []
                for item in triple_results:
                    result_neo4j = item.get("results", {}).get("neo4j", [])
                    ids = {
                        _normalize_label(row.get("diagram_id", ""))
                        for row in result_neo4j
                        if _normalize_label(row.get("diagram_id", ""))
                    }
                    if ids:
                        diagram_sets.append(ids)

                if len(diagram_sets) >= 2:
                    shared_ids = set.intersection(*diagram_sets)
                    for raw_id in sorted(shared_ids):
                        lookup_ids = [raw_id]
                        if not re.search(r"\.(png|jpg|jpeg|webp)$", raw_id):
                            lookup_ids.extend([f"{raw_id}.png", f"{raw_id}.jpg", f"{raw_id}.jpeg", f"{raw_id}.webp"])

                        resolved = None
                        for lookup_id in lookup_ids:
                            diagram_obj = postgres_service.get_diagram(lookup_id)
                            if diagram_obj:
                                resolved = _serialize_diagram(diagram_obj)
                                break

                        if resolved:
                            intersection_diagrams.append(resolved)

            if intersection_diagrams:
                query_results = triple_results
                routing_mode = "triple_intersection"
                triple_summary = ", ".join(
                    [
                        f"{t.get('subject')} {t.get('relationship')} {t.get('object')}"
                        for t in triples[:4]
                    ]
                )
                descriptions = [
                    f"Resolved by shared diagram across triples: {triple_summary}"
                ]
                final_output = _build_final_output(
                    _first_diagram(intersection_diagrams),
                    descriptions,
                    None,
                    triple_focus_terms or subject_terms,
                    query_text or normalized_query_text,
                    model_output=model_output,
                )

            if not final_output:
                merged_descriptions: List[str] = []
                merged_diagrams: List[Dict[str, Any]] = []
                for item in triple_results:
                    merged_descriptions.extend(item.get("results", {}).get("descriptions", []))
                    merged_diagrams.extend(item.get("results", {}).get("diagrams", []))
                if merged_diagrams:
                    unique_diagrams = list({d.get("diagram_id"): d for d in merged_diagrams if d.get("diagram_id")}.values())
                    query_results = triple_results
                    final_output = _build_final_output(
                        _first_diagram(unique_diagrams),
                        merged_descriptions,
                        None,
                        subject_terms,
                        query_text or normalized_query_text,
                        model_output=model_output,
                    )
                else:
                    query_results = []

        if not query_results and normalized_query_text:
            routing_mode = "subject_fallback"
            model_subject_candidates_terms = _safe_terms(
                [item.get("subject_name", "") for item in model_subject_candidates]
            )
            extracted_subject_candidates = _extract_subject_candidates(normalized_query_text)

            # Prefer specific query-derived entities first (e.g., ladybug/dragonfly),
            # then model suggestions; avoid trying generic terms before specific ones.
            subject_candidates = list(
                dict.fromkeys(extracted_subject_candidates + model_subject_candidates_terms)
            )
            subject_candidates = [term for term in subject_candidates if _is_valid_subject_candidate(term)]

            for subject_term in subject_candidates:
                subject_path_result = postgres_service.search_subject_to_category_diagrams(subject_term, limit=25)

                if subject_path_result.get("diagrams") or subject_path_result.get("categories"):
                    descriptions = [
                        f"Resolved subject '{subject.get('subject_name')}' to category-diagram links"
                        for subject in subject_path_result.get("subjects", [])
                    ]
                    diagrams = _first_diagram(subject_path_result.get("diagrams", []))
                    query_results = [
                        {
                            "triple": {
                                "subject": subject_term,
                                "relationship": "related_to",
                                "object": "diagram",
                            },
                            "results": {
                                "postgres": {
                                    "categories": subject_path_result.get("categories", []),
                                    "diagrams": diagrams,
                                },
                                "neo4j": [],
                                "mongo": [],
                                "descriptions": descriptions,
                                "diagrams": diagrams,
                            },
                        }
                    ]
                    first_category = subject_path_result.get("categories", [{}])[0]
                    final_output = _build_final_output(
                        diagrams,
                        descriptions,
                        first_category.get("category_name") if first_category else None,
                        [subject_term],
                        query_text or normalized_query_text,
                        model_output=model_output,
                    )
                    break

        if not query_results and subject_terms:
            routing_mode = "subject_textlabel_global"
            textlabel_diagrams = _search_diagrams_by_subject_textlabels_global(
                neo4j_service,
                postgres_service,
                subject_terms,
                normalized_query_text,
                limit=3,
            )
            if textlabel_diagrams:
                category_name = None
                first_diagram = textlabel_diagrams[0]
                if first_diagram.get("category_id") is not None:
                    try:
                        category_obj = postgres_service.get_category(first_diagram.get("category_id"))
                        category_name = category_obj.name if category_obj else None
                    except Exception:
                        category_name = None

                descriptions = [
                    f"Resolved diagram by TextLabel evidence for subject term(s): {', '.join(subject_terms[:5])}"
                ]
                query_results = [
                    {
                        "triple": {
                            "subject": (normalized_query_text or query_text or "subject").strip(),
                            "relationship": "textlabel_match",
                            "object": textlabel_diagrams[0].get("diagram_id"),
                        },
                        "results": {
                            "postgres": {
                                "categories": [],
                                "diagrams": _first_diagram(textlabel_diagrams),
                            },
                            "neo4j": [],
                            "mongo": [],
                            "descriptions": descriptions,
                            "diagrams": _first_diagram(textlabel_diagrams),
                        },
                    }
                ]
                final_output = _build_final_output(
                    _first_diagram(textlabel_diagrams),
                    descriptions,
                    category_name,
                    subject_terms,
                    query_text or normalized_query_text,
                    model_output=model_output,
                )

        if not query_results:
            routing_mode = "pending_learning"
            pending_learning_item = mongo_service.create_pending_learning_item(
                {
                    "query_type": "mixed" if query_text and image else "image" if image else "text",
                    "query_text": query_text,
                    "normalized_query_text": normalized_query_text,
                    "image_url": saved_image_url,
                    "user_id": user_id,
                    "model_output": model_output,
                    "analysis_case": analysis_case,
                    "analysis_mode": selected_analysis_mode,
                    "reason": "No category/subject/SRO match found in current knowledge base",
                    "status": "pending",
                }
            )

        final_output = _resolve_and_cache_diagram_explanation(
            final_output=final_output,
            mongo_service=mongo_service,
            query_text=query_text,
            normalized_query_text=normalized_query_text,
        )

        if routing_mode == "category_shortcut":
            analysis_case = "case_1_category_keyword"
        elif routing_mode in {"triple", "triple_intersection", "subject_fallback", "subject_textlabel_global", "triple_subject_textlabel", "subject_intersection_priority"}:
            analysis_case = "case_2_subject_or_sro"
        elif routing_mode == "pending_learning":
            analysis_case = "case_3_pending_learning"

        kg_query_ms = round((time.perf_counter() - kg_stage_started_at) * 1000.0, 3)
        total_elapsed_ms = round((time.perf_counter() - request_started_at) * 1000.0, 3)

        log_payload = {
            "type": "mixed" if query_text and image else "image" if image else "text",
            "query_text": query_text,
            "normalized_query_text": normalized_query_text,
            "image_path": saved_image_path,
            "image_url": saved_image_url,
            "user_id": user_id,
            "routing_mode": routing_mode,
            "phase": phase,
            "analysis_case": analysis_case,
            "analysis_mode": selected_analysis_mode,
            "triples": triples,
            "query_results": query_results,
            "final_output": final_output,
            "timing": {
                "model_analysis_ms": model_analysis_ms,
                "kg_query_ms": kg_query_ms,
                "total_elapsed_ms": total_elapsed_ms,
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        log = mongo_service.create_query_log(log_payload)

        return {
            "success": True,
            "log_id": log.get("_id") if log else None,
            "query": {
                "type": log_payload["type"],
                "text": query_text,
                "normalized_text": normalized_query_text,
                "routing_mode": routing_mode,
                "phase": phase,
                "analysis_case": analysis_case,
                "analysis_mode": selected_analysis_mode,
                "image_url": saved_image_url
            },
            "model_output": model_output,
            "triples": triples,
            "query_results": query_results,
            "final_output": final_output,
            "pending_review": pending_learning_item,
            "timing": {
                "model_analysis_ms": model_analysis_ms,
                "kg_query_ms": kg_query_ms,
                "total_elapsed_ms": total_elapsed_ms,
            },
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


@router.get("/query/pending-learning")
def get_pending_learning_items(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Danh sách input chưa match dữ liệu KG để admin review và bổ sung."""
    service = MongoService()
    try:
        items = service.get_pending_learning_items(limit=limit, status=status)
        return {
            "success": True,
            "total": len(items),
            "items": items,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/pending-learning/{item_id}/approve")
def approve_pending_learning_item(
    item_id: str,
    payload: PendingLearningApprovalRequest,
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """Admin duyệt pending item và đồng bộ tri thức mới vào PostgreSQL + Neo4j + MongoDB."""
    mongo_service = MongoService()
    postgres_service = PostgresService(db)
    neo4j_service: Optional[Neo4jService] = None

    pending_item = mongo_service.get_pending_learning_item_by_id(item_id)
    if not pending_item:
        raise HTTPException(status_code=404, detail="Pending learning item not found")

    if pending_item.get("status") == "approved":
        return {
            "success": True,
            "message": "Pending learning item was already approved",
            "item": pending_item,
        }

    inserted: Dict[str, Any] = {
        "root_category": None,
        "category": None,
        "root_subject": None,
        "subjects": [],
        "relationship": None,
        "sro": None,
        "neo4j_subjects_synced": [],
        "neo4j_relationship_synced": False,
        "mongo_semantic_relationship": None,
    }

    try:
        neo4j_service = Neo4jService()

        selected_category_name = payload.category_name
        if not selected_category_name:
            model_output = pending_item.get("model_output") or {}
            category_candidates = model_output.get("category_candidates") or []
            if category_candidates and isinstance(category_candidates[0], dict):
                selected_category_name = category_candidates[0].get("category_name")

        category_obj = None
        if selected_category_name:
            category_obj = _find_category_by_name(postgres_service, selected_category_name)
            if not category_obj:
                root_category_id = "auto_learned"
                root_category = postgres_service.get_root_category(root_category_id)
                if not root_category:
                    root_category = postgres_service.create_root_category(
                        postgres_schemas.RootCategoryCreate(
                            id=root_category_id,
                            name="Auto Learned",
                            description="Categories approved from pending learning queue",
                        )
                    )
                    inserted["root_category"] = {
                        "id": root_category.id,
                        "name": root_category.name,
                    }

                category_obj = postgres_service.create_category(
                    postgres_schemas.CategoryCreate(
                        name=selected_category_name,
                        root_category_id=root_category.id,
                        level=1,
                        description="Approved from pending learning queue",
                    )
                )
                inserted["category"] = {
                    "id": category_obj.id,
                    "name": category_obj.name,
                }

        root_subject_name = payload.root_subject_name or "Auto Learned Subjects"
        root_subject_obj = _find_root_subject_by_name(postgres_service, root_subject_name)
        if not root_subject_obj:
            root_subject_obj = postgres_service.create_root_subject(
                postgres_schemas.RootSubjectCreate(
                    name=root_subject_name,
                    description="Root subject for approved pending-learning terms",
                    level=0,
                )
            )
        inserted["root_subject"] = {
            "id": root_subject_obj.id,
            "name": root_subject_obj.name,
        }

        subject_names = [_normalize_label(name) for name in (payload.subject_names or []) if name and _normalize_label(name)]
        if not subject_names:
            subject_names = _collect_subject_names_from_pending(pending_item)

        if not subject_names:
            normalized_query = _normalize_label(
                pending_item.get("normalized_query_text") or pending_item.get("query_text") or ""
            )
            if normalized_query:
                tokens = [token for token in normalized_query.split() if len(token) >= 3]
                subject_names = tokens[:2]

        if not subject_names:
            raise HTTPException(status_code=400, detail="No subject candidates to approve from pending item")

        persisted_subjects = []
        for subject_name in subject_names[:5]:
            subject_obj = _find_subject_exact(postgres_service, subject_name)
            if not subject_obj:
                categories = [category_obj.name] if category_obj else []
                subject_obj = postgres_service.create_subject(
                    postgres_schemas.SubjectCreate(
                        name=subject_name,
                        root_subject_id=root_subject_obj.id,
                        synonyms=[subject_name],
                        description="Approved from pending learning queue",
                        categories=categories,
                    )
                )
            persisted_subjects.append(subject_obj)
            inserted["subjects"].append({
                "id": subject_obj.id,
                "name": subject_obj.name,
            })

            neo4j_subject = neo4j_service.create_subject(
                {
                    "id": subject_obj.id,
                    "name": subject_obj.name,
                    "root_subject_id": root_subject_obj.id,
                    "synonyms": subject_obj.synonyms or [],
                    "description": subject_obj.description or "",
                    "categories": subject_obj.categories or [],
                }
            )
            if neo4j_subject:
                inserted["neo4j_subjects_synced"].append(subject_obj.id)

        relationship_name = _normalize_label(payload.relationship_name or "") or _collect_relationship_from_pending(pending_item)
        relationship_obj = postgres_service.get_relationship_by_name(relationship_name)
        if not relationship_obj:
            relationship_obj = postgres_service.create_relationship(
                postgres_schemas.RelationshipCreate(
                    name=relationship_name,
                    description="Approved from pending learning queue",
                    semantic_type="learned",
                )
            )
        inserted["relationship"] = {
            "id": relationship_obj.id,
            "name": relationship_obj.name,
        }

        subject_for_sro = persisted_subjects[0]
        object_for_sro = persisted_subjects[1] if len(persisted_subjects) > 1 else persisted_subjects[0]

        diagram_id = None
        if category_obj:
            diagrams = postgres_service.get_diagrams_by_category(category_obj.id, limit=1)
            if diagrams:
                diagram_id = diagrams[0].id

        existing_sro = postgres_service.get_sro_by_triple(
            subject_for_sro.id,
            relationship_obj.id,
            object_for_sro.id,
        )
        if existing_sro:
            sro_obj = existing_sro
        else:
            sro_obj = postgres_service.create_sro(
                postgres_schemas.SROCreate(
                    subject_id=subject_for_sro.id,
                    relationship_id=relationship_obj.id,
                    object_id=object_for_sro.id,
                    diagram_id=diagram_id,
                    confidence_score=0.95,
                    context="Approved from pending-learning queue",
                )
            )

        inserted["sro"] = {
            "id": sro_obj.id,
            "subject_id": sro_obj.subject_id,
            "relationship_id": sro_obj.relationship_id,
            "object_id": sro_obj.object_id,
            "diagram_id": sro_obj.diagram_id,
        }

        neo4j_relationship = neo4j_service.create_subject_relationship(
            from_subject_id=subject_for_sro.id,
            to_subject_id=object_for_sro.id,
            relationship_type=relationship_obj.name.upper().replace(" ", "_"),
            properties={
                "approved_from_pending": True,
                "pending_item_id": item_id,
                "confidence_score": 0.95,
                "diagram_id": diagram_id or "",
            },
        )
        inserted["neo4j_relationship_synced"] = bool(neo4j_relationship)

        if diagram_id and category_obj:
            semantic_doc = mongo_service.create_semantic_relationship(
                SemanticRelationshipCreate(
                    diagram_id=diagram_id,
                    category=category_obj.name,
                    extracted_relationships=[
                        {
                            "subject": subject_for_sro.name,
                            "relationship": relationship_obj.name,
                            "object": object_for_sro.name,
                            "source": "pending-learning-approval",
                        }
                    ],
                )
            )
            inserted["mongo_semantic_relationship"] = semantic_doc.get("_id") if semantic_doc else None

        updated_item = mongo_service.update_pending_learning_item(
            item_id,
            {
                "status": "approved",
                "approved_by": payload.approved_by,
                "approved_note": payload.note,
                "approved_at": datetime.utcnow().isoformat(),
                "approval_result": inserted,
            },
        )

        return {
            "success": True,
            "message": "Pending learning item approved and synced",
            "result": inserted,
            "item": updated_item,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval sync failed: {str(e)}")
    finally:
        if neo4j_service:
            neo4j_service.close()


@router.post("/query/pending-learning/{item_id}/reject")
def reject_pending_learning_item(
    item_id: str,
    payload: PendingLearningRejectRequest
) -> Dict[str, Any]:
    """Admin từ chối pending item và lưu lý do để theo dõi vòng học dữ liệu."""
    mongo_service = MongoService()
    pending_item = mongo_service.get_pending_learning_item_by_id(item_id)

    if not pending_item:
        raise HTTPException(status_code=404, detail="Pending learning item not found")

    current_status = pending_item.get("status")
    if current_status == "approved":
        raise HTTPException(status_code=409, detail="Cannot reject an already approved pending item")

    if current_status == "rejected":
        return {
            "success": True,
            "message": "Pending learning item was already rejected",
            "item": pending_item,
        }

    rejected_item = mongo_service.update_pending_learning_item(
        item_id,
        {
            "status": "rejected",
            "rejected_by": payload.rejected_by,
            "rejected_reason": payload.reason,
            "rejected_note": payload.note,
            "rejected_at": datetime.utcnow().isoformat(),
        },
    )

    return {
        "success": True,
        "message": "Pending learning item rejected",
        "item": rejected_item,
    }


# ========== SRO MANAGEMENT ENDPOINTS ==========

@router.post("/sro/create")
def create_sro_synced(
    subject_id: int,
    relationship_id: int,
    object_id: int,
    diagram_id: Optional[str] = None,
    confidence_score: Optional[float] = None,
    context: Optional[str] = None,
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """
    Create Subject-Relationship-Object triple and sync to both PostgreSQL and Neo4j
    Auto-generates code as S_R_O
    """
    integration_service = IntegrationService(db, None, None)
    
    try:
        result = integration_service.create_sro_synced(
            subject_id=subject_id,
            relationship_id=relationship_id,
            object_id=object_id,
            diagram_id=diagram_id,
            confidence_score=confidence_score,
            context=context
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["errors"])
        
        return {
            "success": True,
            "message": "SRO created and synced successfully",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sro/{sro_id}")
def update_sro_synced(
    sro_id: int,
    subject_id: Optional[int] = None,
    relationship_id: Optional[int] = None,
    object_id: Optional[int] = None,
    diagram_id: Optional[str] = None,
    confidence_score: Optional[float] = None,
    context: Optional[str] = None,
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """
    Update Subject-Relationship-Object triple in both PostgreSQL and Neo4j
    """
    integration_service = IntegrationService(db, None, None)
    
    try:
        result = integration_service.update_sro_synced(
            sro_id=sro_id,
            subject_id=subject_id,
            relationship_id=relationship_id,
            object_id=object_id,
            diagram_id=diagram_id,
            confidence_score=confidence_score,
            context=context
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["errors"])
        
        return {
            "success": True,
            "message": "SRO updated and synced successfully",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sro/{sro_id}")
def delete_sro_synced(
    sro_id: int,
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """
    Delete Subject-Relationship-Object triple from both PostgreSQL and Neo4j
    """
    integration_service = IntegrationService(db, None, None)
    
    try:
        result = integration_service.delete_sro_synced(sro_id)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["errors"])
        
        return {
            "success": True,
            "message": "SRO deleted successfully",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sro/list")
def get_all_sros_with_details(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """
    Get all SROs with full details (subject name, relationship name, object name, codes)
    """
    integration_service = IntegrationService(db, None, None)
    
    try:
        result = integration_service.get_all_sros_with_details(skip=skip, limit=limit)
        
        return {
            "success": True,
            "total": len(result),
            "skip": skip,
            "limit": limit,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sro/{sro_id}")
def get_sro_details(
    sro_id: int,
    db: Session = Depends(get_postgres_db)
) -> Dict[str, Any]:
    """
    Get single SRO with full details
    """
    postgres_service = PostgresService(db)
    
    try:
        sro = postgres_service.get_sro(sro_id)
        if not sro:
            raise HTTPException(status_code=404, detail="SRO not found")
        
        subject = postgres_service.get_subject(sro.subject_id)
        relationship = postgres_service.get_relationship(sro.relationship_id)
        obj = postgres_service.get_subject(sro.object_id)
        
        code = f"{subject.code}_{relationship.code}_{obj.code}"
        
        return {
            "success": True,
            "data": {
                "id": sro.id,
                "code": code,
                "subject_id": sro.subject_id,
                "subject_name": subject.name,
                "subject_code": subject.code,
                "relationship_id": sro.relationship_id,
                "relationship_name": relationship.name,
                "relationship_code": relationship.code,
                "object_id": sro.object_id,
                "object_name": obj.name,
                "object_code": obj.code,
                "diagram_id": sro.diagram_id,
                "confidence_score": float(sro.confidence_score) if sro.confidence_score else None,
                "context": sro.context,
                "created_at": sro.created_at.isoformat() if sro.created_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))