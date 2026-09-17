"""Concrete composition helpers between backend objects and the Agent layer."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Iterable, Mapping, Optional

from .api import create_app
from .config import AgentConfig, load_agent_config
from .memory import SessionStore
from .prompts import RAGPrompt
from .react_loop import AgentModel, GenerationConfig, model_text_and_usage
from .service import AgentService
from .tools import InMemoryPaperCatalog, PaperRecord, ToolRegistry, build_default_tool_registry

from src.backend.rag import RAGService, create_llm_client


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _author_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str) or not value.strip():
        return []
    return [
        item.strip()
        for item in re.split(r"\s*;\s*|\s+and\s+|、|，|,", value)
        if item.strip()
    ]


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and (not isinstance(value, str) or value.strip()):
            return value
    return None


def _parse_year(value: Any) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1800 <= value <= 2200 else None
    if isinstance(value, str):
        pdf_date = re.search(r"(?:^|D:)(19\d{2}|20\d{2})\d{0,10}", value, flags=re.IGNORECASE)
        if pdf_date:
            return int(pdf_date.group(1))
        match = re.search(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", value)
        if match:
            return int(match.group(1))
    return None


def _extract_doi(text: str) -> Optional[str]:
    match = re.search(
        r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+",
        text[:12000],
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(0).rstrip(".,;:)]}")


def _extract_abstract(text: str) -> str:
    match = re.search(
        r"(?:^|\n)\s*abstract\s*:?[ \t]*\n?(.*?)(?=\n\s*(?:keywords?|index terms?|introduction|1[. ):-]*introduction)\b)",
        text[:16000],
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()[:4000]


def _summary_text(source: Any) -> tuple[str, str]:
    if isinstance(source, PaperRecord):
        title = source.title
        text = source.text or "\n".join(
            item for item in (source.abstract, source.method, source.results) if item
        )
    elif isinstance(source, Mapping):
        title = str(source.get("title", ""))
        text = str(source.get("text", ""))
    else:
        title = str(_value(source, "title", ""))
        text = str(_value(source, "text", ""))
    text = text.strip()
    if len(text) > 12000:
        text = text[:9000] + "\n[content truncated]\n" + text[-3000:]
    return title, text


def _json_object(text: str) -> Mapping[str, Any]:
    candidate = text.strip()
    candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s*```$", "", candidate)
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        candidate = candidate[start : end + 1]
    payload = json.loads(candidate)
    if not isinstance(payload, Mapping):
        raise ValueError("summary model output must be a JSON object")
    return payload


def _document_items(source: Any) -> Iterable[Any]:
    """Accept backend Documents, IngestionResult, or a simple iterable."""

    if source is None:
        return []
    items = _value(source, "items")
    if items is not None:
        return [
            _value(item, "document")
            for item in items
            if _value(item, "document") is not None
        ]
    if isinstance(source, Mapping):
        return list(source.values())
    if isinstance(source, (str, bytes)):
        return []
    if _value(source, "document_id") is not None and _value(source, "text") is not None:
        return [source]
    return source


def paper_catalog_from_documents(source: Any) -> InMemoryPaperCatalog:
    """Build paper records from real backend ``Document`` objects.

    Only fields explicitly present in document metadata are copied.  Missing
    authors, years, methods, datasets, or results stay empty instead of being
    guessed from a filename or an LLM response.
    """

    catalog = InMemoryPaperCatalog()
    for document in _document_items(source):
        document_id = _value(document, "document_id")
        file_name = str(_value(document, "file_name", ""))
        if not document_id:
            document_id = file_name or str(_value(document, "id", ""))
        if not document_id:
            continue
        raw_metadata = _value(document, "metadata", {})
        raw_metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
        nested_pdf = raw_metadata.get("pdf_metadata", {})
        nested_pdf = dict(nested_pdf) if isinstance(nested_pdf, Mapping) else {}
        metadata = dict(nested_pdf)
        metadata.update(raw_metadata)
        text = str(_value(document, "text", ""))
        title = _first_present(nested_pdf, "title", "Title")
        if title is None:
            title = _first_present(metadata, "title", "Title")
        authors = _author_list(_first_present(metadata, "authors", "author", "Author"))
        year = _parse_year(
            _first_present(metadata, "year", "publication_year", "published_year", "CreationDate")
        )
        if year is None:
            year = _parse_year(text[:3000])
        doi = _first_present(metadata, "doi", "DOI")
        doi = str(doi).strip() if doi else _extract_doi(text)
        abstract = _first_present(metadata, "abstract", "Abstract")
        abstract = str(abstract).strip() if abstract else _extract_abstract(text)
        extracted_fields = {
            "title": bool(title),
            "authors": bool(authors),
            "year": year is not None,
            "abstract": bool(abstract),
            "doi": bool(doi),
            "method": bool(metadata.get("method")),
            "datasets": bool(metadata.get("datasets")),
            "results": bool(metadata.get("results")),
        }
        record_metadata = dict(raw_metadata)
        record_metadata["agent_extraction"] = {
            "sources": {
                "title": "metadata" if title else None,
                "authors": "metadata" if authors else None,
                "year": "metadata_or_front_matter" if year is not None else None,
                "abstract": "metadata_or_front_matter" if abstract else None,
                "doi": "metadata_or_front_matter" if doi else None,
            },
            "missing_fields": [key for key, present in extracted_fields.items() if not present],
        }
        catalog.add(
            PaperRecord(
                paper_id=str(document_id),
                file_name=file_name,
                title=str(title or ""),
                authors=authors,
                year=year,
                abstract=str(abstract or ""),
                doi=doi,
                method=str(metadata.get("method", "")),
                datasets=_string_list(metadata.get("datasets")),
                results=str(metadata.get("results", "")),
                text=text,
                metadata=record_metadata,
            )
        )
    return catalog


def build_summary_callback(
    llm_client: AgentModel,
    generation_config: Optional[GenerationConfig] = None,
) -> Callable[[str], str]:
    """Create a bounded conversation-summary callback using the existing LLM client."""

    config = generation_config or GenerationConfig(max_output_tokens=256)

    def summarize(transcript: str) -> str:
        prompt = RAGPrompt(
            system=(
                "Summarize the conversation history for a research assistant. "
                "Keep user goals, confirmed facts, unresolved questions, and "
                "paper identifiers. Do not add facts. Return concise plain text."
            ),
            user="Conversation history to compress:\n" + transcript,
        )
        output = llm_client.generate(prompt, config)
        text, usage = model_text_and_usage(output)
        summarize.last_token_usage = dict(usage) if usage else None
        if not text.strip():
            raise ValueError("summary model returned empty text")
        return text.strip()

    summarize.last_token_usage = None  # type: ignore[attr-defined]
    return summarize


def build_paper_summary_callback(
    llm_client: AgentModel,
    generation_config: Optional[GenerationConfig] = None,
) -> Callable[[Any], Mapping[str, Any]]:
    """Create a JSON-only, source-bounded paper summary callback."""

    config = generation_config or GenerationConfig(max_output_tokens=512)

    def summarize(source: Any) -> Mapping[str, Any]:
        title, text = _summary_text(source)
        if not text:
            raise ValueError("paper has no text to summarize")
        prompt = RAGPrompt(
            system=(
                "You summarize a research paper using only the supplied source text. "
                "Return one JSON object with exactly four string fields: background, "
                "method, results, conclusion. If a field is not supported by the source, "
                "return an empty string. Never invent authors, numbers, datasets, or claims."
            ),
            user="Paper title: " + title + "\nSource text:\n" + text,
        )
        output = llm_client.generate(prompt, config)
        response_text, usage = model_text_and_usage(output)
        payload = _json_object(response_text)
        result = {
            "background": str(payload.get("background", "")).strip(),
            "method": str(payload.get("method", "")).strip(),
            "results": str(payload.get("results", "")).strip(),
            "conclusion": str(payload.get("conclusion", "")).strip(),
            "source": "deepseek",
        }
        if usage:
            result["token_usage"] = dict(usage)
        return result

    return summarize


def _default_health_check(
    llm_client: Optional[AgentModel],
    rag_service: Any,
) -> Callable[[], Mapping[str, Any]]:
    def check() -> Mapping[str, Any]:
        retrieval_mode = getattr(rag_service, "retrieval_mode", None)
        effective_llm = (
            llm_client
            if llm_client is not None
            else getattr(rag_service, "llm_client", None)
        )
        api_key_env = getattr(effective_llm, "api_key_env", None)
        llm_ready = bool(effective_llm is not None)
        if api_key_env:
            llm_ready = bool(os.getenv(str(api_key_env)))
        return {
            "llm": "configured" if llm_ready else "not_configured",
            "vector_store": "configured" if rag_service is not None else "not_configured",
            "rag": {
                "status": "configured" if rag_service is not None else "not_configured",
                "retrieval_mode": retrieval_mode,
            },
        }

    return check


def build_agent_service(
    llm_client: Optional[AgentModel],
    rag_service: Any = None,
    documents: Any = None,
    paper_catalog: Any = None,
    search_fn: Optional[Callable[..., Any]] = None,
    summary_fn: Optional[Callable[..., Any]] = None,
    summary_callback: Optional[Callable[[str], str]] = None,
    config: Optional[AgentConfig] = None,
    memory_store: Optional[SessionStore] = None,
    generation_config: Optional[GenerationConfig] = None,
    health_check: Optional[Callable[[], Mapping[str, Any]]] = None,
) -> AgentService:
    """Build the Agent from already-constructed backend dependencies.

    This function performs no model construction and no network request.  The
    caller owns backend index/model lifecycle and passes the live instances in.
    """

    if rag_service is not None:
        if getattr(rag_service, "retrieval_mode", None) != "hybrid_rerank":
            raise ValueError("rag_service.retrieval_mode must be 'hybrid_rerank' for Agent integration")
        rag_llm_client = getattr(rag_service, "llm_client", None)
        if llm_client is not None and rag_llm_client is not None and rag_llm_client is not llm_client:
            raise ValueError("Agent and RAG must share the same llm_client instance")
    agent_config = config or load_agent_config()
    catalog = paper_catalog
    if catalog is None and documents is not None:
        catalog = paper_catalog_from_documents(documents)
    effective_generation = generation_config or GenerationConfig()
    effective_summary = summary_callback
    if effective_summary is None and llm_client is not None:
        effective_summary = build_summary_callback(llm_client, effective_generation)
    effective_paper_summary = summary_fn
    if effective_paper_summary is None and llm_client is not None:
        effective_paper_summary = build_paper_summary_callback(
            llm_client,
            effective_generation,
        )
    registry: ToolRegistry = build_default_tool_registry(
        rag_service=rag_service,
        paper_catalog=catalog,
        search_fn=search_fn,
        summary_fn=effective_paper_summary,
        max_workers=agent_config.max_workers,
    )
    service = AgentService(
        llm_client=llm_client,
        registry=registry,
        memory_store=memory_store,
        config=agent_config,
        generation_config=effective_generation,
        summary_callback=effective_summary,
        health_check=health_check or _default_health_check(llm_client, rag_service),
    )
    # Public composition handle for applications that also expose direct RAG.
    service.rag_service = rag_service
    return service


def create_deepseek_client(
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key_env: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    config: Optional[AgentConfig] = None,
) -> AgentModel:
    """Create the configured DeepSeek-compatible client without network I/O."""

    agent_config = config or load_agent_config()
    llm_config = agent_config.llm
    return create_llm_client(
        provider=llm_config.provider,
        model_name=llm_config.model_name if model_name is None else model_name,
        api_base=llm_config.api_base if api_base is None else api_base,
        api_key_env=llm_config.api_key_env if api_key_env is None else api_key_env,
        timeout_seconds=(
            llm_config.timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        ),
    )


def build_deepseek_agent_service(**kwargs: Any) -> AgentService:
    """Build an Agent with the local DeepSeek configuration and no network call."""

    if "llm_client" in kwargs:
        raise ValueError("build_deepseek_agent_service constructs llm_client; do not pass it")
    config = kwargs.get("config")
    model_name = kwargs.pop("model_name", None)
    api_base = kwargs.pop("api_base", None)
    api_key_env = kwargs.pop("api_key_env", None)
    timeout_seconds = kwargs.pop("timeout_seconds", None)
    llm_client = create_deepseek_client(
        model_name=model_name,
        api_base=api_base,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        config=config if isinstance(config, AgentConfig) else None,
    )
    return build_agent_service(llm_client=llm_client, **kwargs)


def build_deepseek_rag_agent_service(
    retriever: Any,
    *,
    documents: Any = None,
    paper_catalog: Any = None,
    retrieval_mode: str = "hybrid_rerank",
    default_top_k: int = 5,
    allow_llm_fallback: bool = True,
    generation_config: Optional[GenerationConfig] = None,
    config: Optional[AgentConfig] = None,
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key_env: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    client_wrapper: Optional[Callable[[Any], Any]] = None,
    **agent_kwargs: Any,
) -> AgentService:
    """Build RAG and Agent around one DeepSeek client and a hybrid retriever."""

    if retriever is None:
        raise ValueError("retriever is required")
    if retrieval_mode != "hybrid_rerank":
        raise ValueError("retrieval_mode must be 'hybrid_rerank' for Agent integration")
    llm_client = create_deepseek_client(
        model_name=model_name,
        api_base=api_base,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        config=config,
    )
    if client_wrapper is not None:
        llm_client = client_wrapper(llm_client)
    rag_service = RAGService(
        retriever=retriever,
        llm_client=llm_client,
        generation_config=generation_config or GenerationConfig(),
        retrieval_mode=retrieval_mode,
        default_top_k=default_top_k,
        allow_llm_fallback=allow_llm_fallback,
    )
    return build_agent_service(
        llm_client=llm_client,
        rag_service=rag_service,
        documents=documents,
        paper_catalog=paper_catalog,
        config=config,
        generation_config=generation_config,
        **agent_kwargs,
    )


def create_agent_app(**kwargs: Any) -> Any:
    """Convenience wrapper for callers that already have backend instances."""

    return create_app(build_agent_service(**kwargs))


__all__ = [
    "build_agent_service",
    "build_deepseek_agent_service",
    "build_deepseek_rag_agent_service",
    "build_paper_summary_callback",
    "build_summary_callback",
    "create_deepseek_client",
    "create_agent_app",
    "paper_catalog_from_documents",
]
