"""Lazy production composition. Only explicit work loads local models or calls DeepSeek."""
from pathlib import Path
from urllib.parse import urlparse
from src.agent.config import load_agent_config
from src.agent.integration import build_deepseek_rag_agent_service
from src.backend.config import load_config
from src.backend.rag import GenerationConfig
from src.backend.rag.cache import SemanticCache
from src.backend.rag.context_builder import ContextBuilder
from src.backend.exceptions import LLMServiceError

ROOT = Path(__file__).resolve().parents[2]

def friendly_error(error):
    text = str(error).lower()
    if 'before completion' in text:
        return '生成流提前结束，已保留收到的文本，请重试。'
    if 'empty' in text:
        return 'DeepSeek 未返回有效正文，请检查模型配置与输出 Token 上限。'
    if '401' in text or '403' in text or 'authentication' in text:
        return 'DeepSeek 鉴权失败，请检查本地 DEEPSEEK_API_KEY。'
    if '429' in text or 'rate limit' in text:
        return 'DeepSeek 请求限流，请稍后重试。'
    if 'timeout' in text or 'timed out' in text:
        return '服务响应超时，请稍后重试。'
    if 'api key' in text or 'api_key' in text:
        return '尚未配置 DeepSeek API Key，请刷新页面后重新验证。'
    return '服务暂时不可用，请检查依赖、网络和模型配置后重试。'


def local_dependency_error(error):
    """Return an actionable local-only error without exposing arbitrary details."""
    chain = []
    current = error
    while current is not None:
        chain.append(str(current).lower())
        current = current.__cause__ or current.__context__
    text = ' '.join(chain)
    missing = []
    for marker, package in (
        ('sentence-transformers', 'sentence-transformers'),
        ('sentence_transformers', 'sentence-transformers'),
        ('chromadb', 'chromadb'),
        ('faiss', 'faiss-cpu'),
        ('rank_bm25', 'rank-bm25'),
        ('torch', 'torch'),
    ):
        if marker in text and package not in missing:
            missing.append(package)
    if missing:
        return '缺少本地依赖：' + '、'.join(missing)
    return '本地检索初始化失败，请检查模型文件与依赖。'

class SafeClient:
    """Strip provider bodies before they reach backend logs, traces or SQLite."""
    def __init__(self, client):
        self.client = client
        for name in ('model_name', 'api_base', 'api_key_env', 'timeout_seconds'):
            setattr(self, name, getattr(client, name))

    def generate(self, prompt, config):
        try:
            return self.client.generate(prompt, config)
        except Exception as exc:
            raise LLMServiceError(friendly_error(exc)) from None

    def stream(self, prompt, config):
        try:
            yield from self.client.stream(prompt, config)
        except Exception as exc:
            raise LLMServiceError(friendly_error(exc)) from None

class EmptyRetriever:
    def retrieve(self, query, mode='hybrid_rerank', top_k=5):
        return []

class BackendResources:
    def __init__(self, root):
        self.root = Path(root)
        self.config = load_config(ROOT / 'config/backend.yaml')
        self.embedding = None
        self.store = None
        self.reranker = None

    def ensure(self):
        if self.store is not None:
            return
        from src.backend.embeddings import EmbeddingService
        from src.backend.vectorstores import create_vector_store
        from src.backend.retrieval.reranker import Reranker
        c = self.config
        self.embedding = EmbeddingService(c.embedding.model_name, batch_size=c.embedding.batch_size, normalize_embeddings=c.embedding.normalize_embeddings)
        self.store = create_vector_store(c.vector_store.type, str(self.root / 'indexes'), 'cowork_workspace', c.vector_store.faiss_num_threads)
        self.reranker = Reranker(c.retrieval.reranker_model_name, batch_size=c.retrieval.reranker_batch_size)

    def assemble(self, documents):
        if not documents:
            return EmptyRetriever()
        self.ensure()
        from src.backend.chunking import chunk_document
        from src.backend.retrieval.vector_retriever import VectorRetriever
        from src.backend.retrieval.bm25_retriever import BM25Retriever
        from src.backend.retrieval.hybrid_retriever import HybridRetriever
        c = self.config
        chunks = [chunk for doc in documents for chunk in chunk_document(doc, strategy=c.chunking.strategy, chunk_size=c.chunking.chunk_size, chunk_overlap=c.chunking.chunk_overlap)]
        # Upsert persisted vectors lazily; embeddings are only generated for new/missing documents.
        from src.backend.indexing import IncrementalIndex
        index = IncrementalIndex(self.store, self.embedding, str(self.root / 'manifest.json'), c.chunking.strategy, c.chunking.chunk_size, c.chunking.chunk_overlap)
        index.index_documents(documents)
        return HybridRetriever(VectorRetriever(self.store, self.embedding), BM25Retriever(chunks), self.reranker,
            vector_top_k=c.retrieval.vector_top_k, bm25_top_k=c.retrieval.bm25_top_k,
            final_top_k=c.retrieval.final_top_k, rrf_k=c.retrieval.rrf_k, reranker_top_n=c.retrieval.reranker_top_n)

    def reset_manifest(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'manifest.json').write_text('{}', encoding='utf-8')

    def remove(self, document):
        import json
        self.ensure()
        self.store.delete_document(document.document_id)
        self.store.persist()
        path = self.root / 'manifest.json'
        manifest = json.loads(path.read_text()) if path.exists() else {}
        manifest = {k: v for k, v in manifest.items() if v != document.document_id}
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(manifest), encoding='utf-8')
        temporary.replace(path)

    def chunk_count(self, document):
        from src.backend.chunking import chunk_document
        c = self.config.chunking
        return len(chunk_document(document, strategy=c.strategy, chunk_size=c.chunk_size, chunk_overlap=c.chunk_overlap))


def compose(retriever, documents, memory, version, embedding=None):
    """Use the existing factory and expose its RAG instance through an additive hook."""
    config = load_agent_config(ROOT / 'config/agent.yaml')
    if urlparse(config.llm.api_base).hostname != 'api.deepseek.com' or config.llm.api_key_env != 'DEEPSEEK_API_KEY':
        raise ValueError('工作台只允许 DeepSeek API 和 DEEPSEEK_API_KEY 配置')
    backend = load_config(ROOT / 'config/backend.yaml')
    generation = GenerationConfig(temperature=backend.rag.temperature, top_p=backend.rag.top_p,
                                  max_output_tokens=backend.rag.max_output_tokens)
    agent = build_deepseek_rag_agent_service(retriever, documents=documents, memory_store=memory,
        config=config, generation_config=generation, default_top_k=backend.retrieval.final_top_k,
        allow_llm_fallback=backend.rag.allow_llm_fallback, client_wrapper=SafeClient)
    rag = agent.rag_service
    rag.context_builder = ContextBuilder(max_chars=backend.rag.max_context_chars)
    rag.low_relevance_threshold = backend.rag.low_relevance_threshold
    rag.knowledge_base_version = version
    if embedding is not None and backend.cache.enabled:
        rag.cache = SemanticCache(embedding.embed_query, backend.cache.similarity_threshold, backend.cache.max_entries)
    return agent, rag
