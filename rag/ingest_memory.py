import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

load_dotenv()

ROOT = Path('/home/kspoopoo/.openclaw/workspace')
FILES = [ROOT / 'MEMORY.md', *sorted((ROOT / 'memory').glob('*.md'))]
COL = os.getenv('QDRANT_COLLECTION', 'openclaw-memory')
EMBED_MODEL = os.getenv('EMBED_MODEL', 'text-embedding-3-small')

q = QdrantClient(url=os.getenv('QDRANT_URL', 'http://127.0.0.1:6333'))
ai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def chunk_text(text, size=1200, overlap=120):
    out = []
    i = 0
    while i < len(text):
        out.append(text[i:i+size])
        i += max(1, size - overlap)
    return out

# create collection if needed
try:
    q.get_collection(COL)
except Exception:
    q.create_collection(COL, vectors_config=VectorParams(size=1536, distance=Distance.COSINE))

points = []
pid = 1
for fp in FILES:
    if not fp.exists():
        continue
    txt = fp.read_text(encoding='utf-8', errors='ignore')
    for idx, ch in enumerate(chunk_text(txt)):
        emb = ai.embeddings.create(model=EMBED_MODEL, input=ch).data[0].embedding
        points.append(PointStruct(
            id=pid,
            vector=emb,
            payload={
                'path': str(fp),
                'chunk_index': idx,
                'text': ch,
            }
        ))
        pid += 1

if points:
    q.upsert(collection_name=COL, points=points)
print(f'upserted={len(points)} into {COL}')
