.PHONY: penguin-now penguin-top20 rag-index rag-query acp-status

penguin-now:
	python3 active/market-monitor/penguin_monitor.py --once

penguin-top20:
	python3 active/market-monitor/penguin_top20_flow.py

rag-index:
	cd active/rag && source .venv/bin/activate && python ingest_memory.py

rag-query:
	@if [ -z "$(Q)" ]; then echo "Usage: make rag-query Q='query text'"; exit 1; fi
	cd active/rag && source .venv/bin/activate && python query_memory.py "$(Q)"

acp-status:
	cd /home/kspoopoo/acp-lab/openclaw-acp && npx tsx bin/acp.ts sell list && npx tsx bin/acp.ts serve status
