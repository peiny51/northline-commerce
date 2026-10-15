"""Local Markdown policy loader; store policies, not copied eBay/Olist data."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
POLICIES_DIR = ROOT / 'data' / 'policies'


def read_documents():
    sources = json.loads((POLICIES_DIR / 'sources.json').read_text(encoding='utf-8'))
    documents = {}
    for source in sources:
        doc_id = source['document_id']
        if doc_id in documents:
            raise ValueError(f'Duplicate document ID: {doc_id}')
        path = POLICIES_DIR / 'notes' / f'{doc_id}.md'
        content = path.read_text(encoding='utf-8').strip()
        if not content:
            raise ValueError(f'Empty policy document: {path}')
        metadata = {key: source.get(key, '') for key in ('document_id', 'title', 'category', 'source', 'source_url')}
        digest = hashlib.sha256(json.dumps([content, metadata], sort_keys=True,
                                           ensure_ascii=False).encode('utf-8')).hexdigest()
        documents[doc_id] = (content, metadata, digest)
    return documents


def split_document(content, metadata):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120,
                                               separators=['\n## ', '\n### ', '\n\n', '\n', ' ', ''],
                                               keep_separator='start')
    return [(text, dict(metadata, chunk_id=f'{metadata["document_id"]}-{i}', chunk_index=i))
            for i, text in enumerate(splitter.split_text(content))]
