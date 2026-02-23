# RAG Playbook (Local)

## Start services
```bash
cd active/rag
sudo docker-compose up -d
```

## Index memory
```bash
cd active/rag
source .venv/bin/activate
python ingest_memory.py
```

## Query
```bash
cd active/rag
source .venv/bin/activate
python query_memory.py "질문"
```

## Notes
- 임베딩: local-hash-384 (API 키 불필요)
- 상태 파일: `active/rag/.ingest_manifest.json`
