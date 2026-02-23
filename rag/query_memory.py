import os, sys
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

load_dotenv()
COL = os.getenv('QDRANT_COLLECTION', 'openclaw-memory')
EMBED_MODEL = os.getenv('EMBED_MODEL', 'text-embedding-3-small')
q = QdrantClient(url=os.getenv('QDRANT_URL', 'http://127.0.0.1:6333'))
ai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

query = ' '.join(sys.argv[1:]).strip() or '최근 결정사항 요약'
vec = ai.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding
hits = q.search(collection_name=COL, query_vector=vec, limit=5)
for i,h in enumerate(hits,1):
    p = h.payload
    print(f"[{i}] score={h.score:.4f} {p.get('path')}#{p.get('chunk_index')}")
    print((p.get('text') or '')[:300].replace('\n',' '))
    print('---')
