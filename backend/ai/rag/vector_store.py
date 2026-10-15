"""Persistent Qdrant hybrid collection with safe incremental policy synchronization."""
import os
import uuid
from backend.ai.settings import Config

DENSE = 'dense'
SPARSE = 'sparse'
SPARSE_MODEL = 'Qdrant/bm25'


def client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=Config.QDRANT_URL, timeout=30)


def dense_model():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=Config.EMBEDDING_MODEL)


def sparse_model():
    from fastembed import SparseTextEmbedding
    return SparseTextEmbedding(model_name=SPARSE_MODEL)


def stable_id(chunk_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'outdoor-policies:{chunk_id}'))


def plan_sync(documents, indexed):
    """Return changed and deleted document IDs without touching any Embedding API.

    Metadata stores (document_hash, embedding_model, chunk count) for the first
    point of each document. Missing/older metadata forces a safe refresh.
    """
    changed = {doc_id for doc_id, (_, _, digest) in documents.items()
               if indexed.get(doc_id) != (digest, Config.EMBEDDING_MODEL)}
    deleted = set(indexed) - set(documents)
    return changed, deleted


def stored_chunks(qdrant):
    from qdrant_client import models
    existing = {}
    offset = None
    while True:
        batch, offset = qdrant.scroll(collection_name=Config.QDRANT_COLLECTION,
                                      limit=256, offset=offset, with_payload=True,
                                      with_vectors=False)
        for point in batch:
            payload = point.payload or {}
            doc_id = payload.get('document_id')
            if doc_id:
                entry = existing.setdefault(doc_id, {'ids': [], 'hash': payload.get('document_hash'),
                                                      'model': payload.get('embedding_model')})
                entry['ids'].append(point.id)
                if entry['hash'] != payload.get('document_hash') or entry['model'] != payload.get('embedding_model'):
                    entry['hash'] = None
        if offset is None:
            break
    return existing


def sync_documents():
    """Explicit maintenance command. Normal Flask startup never indexes documents."""
    from qdrant_client import models
    from backend.ai.rag.ingestion import read_documents, split_document
    docs = read_documents()
    if not docs:
        raise RuntimeError('No policies found: refusing to clear the index')
    qdrant = client()
    exists = qdrant.collection_exists(Config.QDRANT_COLLECTION)
    indexed = stored_chunks(qdrant) if exists else {}
    changed, deleted = plan_sync(docs, {k: (v['hash'], v['model']) for k, v in indexed.items()})
    if not changed and not deleted:
        print('No policy changes. Skipped all embedding calls.')
        return {'changed': 0, 'deleted': 0, 'embedded_chunks': 0}

    dense = dense_model() if changed else None
    sparse = sparse_model() if changed else None
    written = 0
    # Embeddings happen before old chunks are removed, so a failed API call
    # cannot erase a previously indexed policy document.
    staged = {}
    for doc_id in sorted(changed):
        content, meta, digest = docs[doc_id]
        chunks = split_document(content, meta)
        texts = [text for text, _ in chunks]
        dense_vecs = dense.embed_documents(texts)
        sparse_vecs = list(sparse.embed(texts))
        if len(dense_vecs) != len(texts) or len(sparse_vecs) != len(texts):
            raise RuntimeError('Embedding count mismatch')
        if not exists:
            qdrant.create_collection(
                collection_name=Config.QDRANT_COLLECTION,
                vectors_config={DENSE: models.VectorParams(size=len(dense_vecs[0]),
                                                            distance=models.Distance.COSINE)},
                sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)})
            exists = True
        else:
            conf = qdrant.get_collection(Config.QDRANT_COLLECTION).config.params.vectors
            size = conf[DENSE].size
            if size != len(dense_vecs[0]):
                raise RuntimeError('Embedding dimension changed. Create a new collection and reindex.')
        points = []
        for (text, metadata), dv, sv in zip(chunks, dense_vecs, sparse_vecs):
            points.append(models.PointStruct(
                id=stable_id(metadata['chunk_id']),
                vector={DENSE: dv, SPARSE: models.SparseVector(indices=sv.indices.tolist(),
                                                                values=sv.values.tolist())},
                payload={'text': text, **metadata, 'document_hash': digest,
                         'embedding_model': Config.EMBEDDING_MODEL}))
        staged[doc_id] = points

    for doc_id, points in staged.items():
        qdrant.upsert(collection_name=Config.QDRANT_COLLECTION, points=points, wait=True)
        written += len(points)
        old_ids = set(indexed.get(doc_id, {}).get('ids', []))
        remaining_ids = old_ids - {p.id for p in points}
        if remaining_ids:
            qdrant.delete(Config.QDRANT_COLLECTION,
                          points_selector=models.PointIdsList(points=list(remaining_ids)), wait=True)
    for doc_id in deleted:
        qdrant.delete(Config.QDRANT_COLLECTION,
                      points_selector=models.PointIdsList(points=indexed[doc_id]['ids']), wait=True)
    print(f'Updated {len(changed)} documents, deleted {len(deleted)} documents, embedded {written} chunks.')
    return {'changed': len(changed), 'deleted': len(deleted), 'embedded_chunks': written}


def search_hybrid(query, limit=10, prefetch_limit=15):
    """Dense + BM25 sparse retrieval, merged with reciprocal-rank fusion."""
    from qdrant_client import models
    qdrant = client()
    if not qdrant.collection_exists(Config.QDRANT_COLLECTION):
        raise RuntimeError('Policy collection is missing. Run python -m scripts.sync_documents.')
    dv = dense_model().embed_query(query)
    sv = next(sparse_model().embed([query]))
    response = qdrant.query_points(
        collection_name=Config.QDRANT_COLLECTION,
        prefetch=[models.Prefetch(query=dv, using=DENSE, limit=prefetch_limit),
                  models.Prefetch(query=models.SparseVector(indices=sv.indices.tolist(),
                                                             values=sv.values.tolist()),
                                  using=SPARSE, limit=prefetch_limit)],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit, with_payload=True)
    return response.points
