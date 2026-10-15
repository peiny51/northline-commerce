"""Cross-encoder reranking of reciprocal-rank-fused policy candidates."""
from functools import lru_cache

@lru_cache(maxsize=1)
def get_reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    return TextCrossEncoder(model_name='Xenova/ms-marco-MiniLM-L-6-v2')


def rerank_results(query, results, limit=5):
    if not results:
        return []
    scores = list(get_reranker().rerank(query, [p.payload['text'] for p in results]))
    return sorted(zip(results, scores), key=lambda pair: float(pair[1]), reverse=True)[:limit]
