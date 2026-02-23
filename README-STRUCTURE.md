# Workspace Structure

이 워크스페이스는 "지금/과거/기억/재사용"을 분리해서 운영합니다.

## Folders

- `active/` : 현재 사용/운영 중인 코드
  - `active/acp/`
  - `active/market-monitor/`
  - `active/rag/`
- `archive/` : 과거 버전/중단된 실험 (삭제 대신 이동)
- `state/` : 실행 결과물, 리포트, 상태 파일
- `playbooks/` : 반복 작업 절차서(SOP)
- `memory/` : 날짜별 메모

## Rules

1. 새 파일이 생기면 5초 분류
   - 지금 쓰는 코드 → `active/`
   - 과거 코드/백업 → `archive/`
   - 실행 산출물/리포트 → `state/`
   - 반복 절차 문서 → `playbooks/`
2. 루트에는 정체성/운영 핵심 문서만 유지
3. 삭제보다 이동(archive)

## Current Active Assets

- `active/market-monitor/penguin_monitor.py`
- `active/market-monitor/penguin_insider_probe.py`
- `active/market-monitor/penguin_14d_analysis.py`
- `active/rag/*` (Qdrant + 로컬 임베딩 RAG)
