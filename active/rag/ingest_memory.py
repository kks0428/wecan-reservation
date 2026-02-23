import hashlib
import json
import math
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

load_dotenv()

ROOT = Path('/home/kspoopoo/.openclaw/workspace')
FILES = [ROOT / 'MEMORY.md', *sorted((ROOT / 'memory').glob('*.md'))]
COL = os.getenv('QDRANT_COLLECTION', 'openclaw-memory')
EMBED_MODEL = os.getenv('EMBED_MODEL', 'local-hash-384')
MANIFEST = ROOT / 'rag' / '.ingest_manifest.json'
VECTOR_SIZE = 384

q = QdrantClient(url=os.getenv('QDRANT_URL', 'http://127.0.0.1:6333'))


def chunk_text(text: str, size: int = 1200, overlap: int = 120):
    out = []
    i = 0
    while i < len(text):
        out.append(text[i:i + size])
        i += max(1, size - overlap)
    return out


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8', errors='ignore')).hexdigest()


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


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_manifest(data: dict):
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


try:
    q.get_collection(COL)
except Exception:
    q.create_collection(COL, vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE))

manifest = load_manifest()
new_manifest = {}
points = []

for fp in FILES:
    if not fp.exists():
        continue
    txt = fp.read_text(encoding='utf-8', errors='ignore')
    chunks = chunk_text(txt)
    for idx, ch in enumerate(chunks):
        key = f"{fp}#{idx}"
        h = sha1(ch)
        new_manifest[key] = h

        if manifest.get(key) == h:
            continue

        emb = local_embed(ch)
        pid = int(hashlib.md5(key.encode()).hexdigest()[:12], 16)
        points.append(PointStruct(
            id=pid,
            vector=emb,
            payload={
                'path': str(fp),
                'chunk_index': idx,
                'text': ch,
            }
        ))

if points:
    q.upsert(collection_name=COL, points=points)

save_manifest(new_manifest)
print(f'updated_points={len(points)} collection={COL} model={EMBED_MODEL}')
