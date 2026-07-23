"""PostgreSQL retrieval for the existing SIOU knowledge base.

The Render database already contains `documents` and `document_chunks` from the
SIOU corpus. Some rows may not have pgvector embeddings, so retrieval must not
depend on a local HuggingFace model or on a specific vector dimension. The V1
search below uses PostgreSQL French full-text search with an ILIKE fallback.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_SEARCH_PLANS = 4
MIN_CANDIDATES_PER_PLAN = 6


def split_administrative_document(
    document_text: str,
    headers_to_split_on: list[tuple[str, str]] | None = None,
    chunk_size: int = 400,
    chunk_overlap: int = 40,
) -> list[Any]:
    from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

    if headers_to_split_on is None:
        headers_to_split_on = [
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ]

    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_sections = markdown_splitter.split_text(document_text)
    section_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\nArticle ", "\nArticle ", "\n\n", "\n", ". ", "! ", "? ", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    combined_chunks: list[Document] = []
    for section in md_sections:
        section_chunks = section_splitter.create_documents([section.page_content])
        for chunk in section_chunks:
            chunk.metadata.update(section.metadata)
            combined_chunks.append(chunk)
    return combined_chunks


_SEARCH_SQL = text(
    """
    WITH terms AS (
        SELECT term
        FROM regexp_split_to_table(:terms_text, E'\\n') AS term
        WHERE term <> ''
    ),
    term_count AS (
        SELECT count(*)::float AS total FROM terms
    ),
    fulltext AS (
        SELECT
            dc.id,
            dc.document_id,
            dc.content,
            dc.page_start AS page_number,
            ts_rank_cd(dc.search_tsv, to_tsquery('french', :ts_query)) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.status IN ('publie', 'valide')
          AND dc.search_tsv @@ to_tsquery('french', :ts_query)
        ORDER BY score DESC
        LIMIT :candidate_limit
    ),
    lexical AS (
        SELECT
            dc.id,
            dc.document_id,
            dc.content,
            dc.page_start AS page_number,
            (
                count(terms.term)::float / NULLIF((SELECT total FROM term_count), 0)
            ) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        JOIN terms ON unaccent(lower(dc.content)) ~ ('\\m' || terms.term || '\\M')
        WHERE d.status IN ('publie', 'valide')
        GROUP BY dc.id, dc.document_id, dc.content, dc.page_start
        HAVING count(terms.term) >= :required_terms
        ORDER BY score DESC, length(dc.content) ASC
        LIMIT :candidate_limit
    )
    SELECT
        id,
        document_id,
        content,
        page_number,
        max(score) AS score
    FROM (
        SELECT * FROM fulltext
        UNION ALL
        SELECT * FROM lexical
    ) ranked
    GROUP BY id, document_id, content, page_number
    ORDER BY score DESC
    LIMIT :top_k
    """
)


async def retrieve_hybrid_chunks(
    db_session: AsyncSession,
    query_text: str,
    embedding_model: Any | None = None,
    top_k: int = 3,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    del embedding_model, rrf_k
    words = _significant_words(query_text)
    if not words:
        return []

    search_plans = _search_plans(query_text, words)[:MAX_SEARCH_PLANS]
    merged_rows: dict[Any, dict[str, Any]] = {}
    for plan_index, (plan_words, required_terms) in enumerate(search_plans):
        rows = await _run_search(
            db_session=db_session,
            words=plan_words,
            required_terms=required_terms,
            top_k=max(top_k, MIN_CANDIDATES_PER_PLAN),
        )
        plan_weight = 1.0 / (plan_index + 1)
        for row in rows:
            row_dict = dict(row)
            row_id = row_dict["id"]
            weighted_score = float(row_dict.get("score") or 0.0) + plan_weight
            existing = merged_rows.get(row_id)
            if existing is None or weighted_score > float(existing.get("_weighted_score") or 0.0):
                row_dict["_weighted_score"] = weighted_score
                merged_rows[row_id] = row_dict

    if not merged_rows:
        return []

    rows = list(merged_rows.values())
    rows = _rerank_rows(query_text, rows)
    rows = rows[:top_k]
    max_score = max(float(row.get("_weighted_score") or row["score"] or 0.0) for row in rows) or 1.0
    return [
        {
            "chunk_id": row["id"],
            "document_id": row["document_id"],
            "content": row["content"],
            "page_number": row["page_number"],
            "score": float(row["score"] or 0.0),
            "similarity": min(1.0, max(0.0, float(row.get("_weighted_score") or row["score"] or 0.0) / max_score)),
        }
        for row in rows
    ]


async def _run_search(
    db_session: AsyncSession,
    words: list[str],
    required_terms: int,
    top_k: int,
) -> list[Any]:
    ts_query = " & ".join(words)
    result = await db_session.execute(
        _SEARCH_SQL,
        {
            "ts_query": ts_query,
            "terms_text": "\n".join(words),
            "required_terms": required_terms,
            "candidate_limit": max(20, top_k * 5),
            "top_k": top_k,
        },
    )
    return list(result.mappings().all())


def _strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _significant_words(value: str) -> list[str]:
    stop_words = {
        "qui",
        "que",
        "quoi",
        "dont",
        "dans",
        "pour",
        "avec",
        "une",
        "des",
        "les",
        "est",
        "sont",
        "etre",
        "être",
        "chargé",
        "charge",
    }
    stop_words.update({"moi", "quel", "quelle", "son", "ses", "sur", "information", "informations"})
    normalized = _strip_accents(value.lower())
    words = re.findall(r"[a-z0-9]{4,}", normalized)
    return [word for word in dict.fromkeys(words) if word not in stop_words][:12]


def _search_plans(query_text: str, words: list[str]) -> list[tuple[list[str], int]]:
    """Construit des recherches successives, du plus strict au plus intentionnel.

    La première recherche conserve le comportement historique. Les suivantes
    reformulent les intentions courantes d'un usager (adresse, rôle, missions)
    en termes réellement présents dans les documents, sans élargir au-delà du
    corpus : elles aident seulement PostgreSQL à trouver le bon chunk.
    """
    strict_words = words[:6]
    relaxed_required = min(len(words), 2) if len(words) > 1 else 1
    required_terms = len(strict_words) if len(strict_words) <= 3 else max(3, len(strict_words) - 1)

    plans: list[tuple[list[str], int]] = [(strict_words, required_terms)]
    if relaxed_required < required_terms:
        plans.append((words, relaxed_required))

    normalized_query = _strip_accents(query_text.lower())
    subject_words = _expand_subject_words(normalized_query, words)
    if subject_words != words:
        plans.append((subject_words[:10], min(2, len(subject_words))))

    expanded_words = _expand_intent_words(normalized_query, words)
    if expanded_words != words:
        # Une recherche intentionnelle doit rester exigeante sur le sujet
        # principal, mais ne doit pas échouer parce que l'usager dit "trouve"
        # là où le document dit "adresse" ou "située".
        subject_expanded = _expand_subject_words(normalized_query, expanded_words)
        plans.append((subject_expanded[:12], min(3, max(1, len(subject_expanded) // 2))))
        plans.append((subject_expanded[:12], min(2, len(subject_expanded))))
        plans.append((expanded_words[:10], min(2, len(expanded_words))))

    deduped: list[tuple[list[str], int]] = []
    seen: set[tuple[tuple[str, ...], int]] = set()
    for plan_words, required in plans:
        if not plan_words:
            continue
        key = (tuple(plan_words), required)
        if key not in seen:
            deduped.append((plan_words, required))
            seen.add(key)
    return deduped


def _expand_subject_words(normalized_query: str, words: list[str]) -> list[str]:
    expanded = list(words)
    word_set = set(words)

    def add(*terms: str) -> None:
        for term in terms:
            if term not in expanded:
                expanded.append(term)

    if "asin" in word_set or "agence des systemes" in normalized_query:
        add("asin", "agence", "systemes", "information", "numerique")
    if "sbin" in word_set or "societe beninoise" in normalized_query:
        add("sbin", "societe", "beninoise", "infrastructures", "numeriques")
    if "mnd" in word_set or "ministere du numerique" in normalized_query:
        add("mnd", "ministere", "numerique", "digitalisation")
    if "siou" in word_set:
        add("siou", "orientation", "usagers", "assistant")

    return expanded[:12]


def _expand_intent_words(normalized_query: str, words: list[str]) -> list[str]:
    expanded = list(words)
    word_set = set(words)

    def add(*terms: str) -> None:
        for term in terms:
            if term not in expanded:
                expanded.append(term)

    asks_location = any(term in word_set for term in {"trouve", "situe", "situee", "adresse", "localisation"}) or "ou se" in normalized_query
    asks_role = any(term in word_set for term in {"role", "mission", "missions", "attribution", "attributions"})
    asks_action = "que fait" in normalized_query or "a quoi sert" in normalized_query
    asks_overview = _asks_overview(normalized_query, word_set)
    asks_services = any(term in word_set for term in {"service", "services", "composee", "composition"})

    if asks_location:
        add("adresse", "localisation", "situee", "situe", "siege", "immeuble", "quartier", "cotonou")
    if asks_role or asks_action or asks_overview:
        add(
            "role",
            "mission",
            "missions",
            "attributions",
            "presentation",
            "definition",
            "charge",
            "operateur",
            "infrastructures",
            "telecommunications",
            "numeriques",
        )
    if asks_services:
        add("services", "composee", "secretariat", "direction", "administration")

    return expanded[:12]


def _asks_overview(normalized_query: str, word_set: set[str]) -> bool:
    overview_terms = {
        "parle",
        "parler",
        "presente",
        "presenter",
        "explique",
        "expliquer",
        "resume",
        "resumer",
        "quoi",
        "definition",
    }
    return (
        bool(word_set & overview_terms)
        or "c est quoi" in normalized_query
        or "c'est quoi" in normalized_query
        or "dis moi" in normalized_query
        or "dit moi" in normalized_query
    )


def _rerank_rows(query_text: str, rows: list[Any]) -> list[Any]:
    normalized_query = _strip_accents(query_text.lower())

    subject_phrases = [
        "agence des systemes d'information et du numerique",
        "agence des systemes d information et du numerique",
        "agence des systemes d'information du numerique",
        "agence des systemes d information du numerique",
        "direction du numerique",
        "direction de la digitalisation",
        "sbin",
        "asin",
    ]
    expected_phrases = [phrase for phrase in subject_phrases if phrase in normalized_query]
    if not expected_phrases:
        return rows
    query_words = set(re.findall(r"[a-z0-9]{4,}", normalized_query))
    is_overview = _asks_overview(normalized_query, query_words)
    asks_location = any(term in query_words for term in {"trouve", "situe", "situee", "adresse", "localisation"}) or "ou se" in normalized_query

    def rank(row: Any) -> tuple[float, float]:
        content = _strip_accents(str(row["content"]).lower())
        phrase_boost = sum(1.0 for phrase in expected_phrases if phrase in content)
        acronym_boost = 0.0
        if ("sbin" in expected_phrases or "sbin" in query_words) and re.search(r"\bsbin\b", content):
            acronym_boost += 0.5
        if ("asin" in expected_phrases or "asin" in query_words) and (
            re.search(r"\basin\b", content) or "agence des systemes" in content
        ):
            acronym_boost += 0.5
        intent_boost = 0.0
        if is_overview:
            intent_boost += sum(0.35 for term in ("mission", "missions", "attribution", "attributions", "role", "bras operationnel") if term in content)
        if asks_location:
            intent_boost += sum(0.35 for term in ("adresse", "localisation", "situee", "situe", "siege", "immeuble", "quartier", "cotonou") if term in content)
        return (phrase_boost + acronym_boost + intent_boost, float(row.get("_weighted_score") or row["score"] or 0.0))

    return sorted(rows, key=rank, reverse=True)
