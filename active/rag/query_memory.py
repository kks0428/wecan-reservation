import hashlib
import math
import os
import re
import sys

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

COL = os.getenv('QDRANT_COLLECTION', 'openclaw-memory')
VECTOR_SIZE = 384

q = QdrantClient(url=os.getenv('QDRANT_URL', 'http://127.0.0.1:6333'))


def tokenize(text: str):
    return re.findall(r"[\w가-힣#@.+-]{2,}", text.lower())


def local_embed(text: str, dim: int = VECTOR_SIZE):
    vec = [0.0] * dim
    toks = tokenize(text)
    if not toks:
        return vec
    for t in toks:
        h = hashlib.md5(t.encode('utf-8')).digest()
        idx = int.from_bytes(h[:2], 'little') % dim
        sign = 1.0 if (h[2] % 2 == 0) else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


query = ' '.join(sys.argv[1:]).strip() or '최근 결정사항 요약'
vec = local_embed(query)

hits = q.search(collection_name=COL, query_vector=vec, limit=5)
for i, h in enumerate(hits, 1):
    p = h.payload
    print(f"[{i}] score={h.score:.4f} {p.get('path')}#{p.get('chunk_index')}")
    print((p.get('text') or '')[:300].replace('\n', ' '))
    print('---')
