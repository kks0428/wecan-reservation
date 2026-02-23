# Ops Efficiency Playbook

## 목적
긴 채팅 컨텍스트를 줄이고, 반복 작업을 빠르게 실행하기 위한 운영 규칙.

## 기본 원칙
1. 긴 출력은 채팅에 다 붙이지 않고 `state/` 파일로 저장.
2. 반복 점검은 `Makefile` 명령으로 실행.
3. 대화 중간중간 상태를 5~10줄로 요약해서 유지.

## 빠른 명령
- 현재 시황: `make penguin-now`
- 상위 지갑 흐름: `make penguin-top20`
- RAG 인덱싱: `make rag-index`
- RAG 질의: `make rag-query Q='질문'`
- ACP 상태: `make acp-status`

## 권장 루틴
- 분석 시작 전: `make penguin-now`
- 의심 구간 확인: `make penguin-top20`
- 결론 저장: `state/`에 리포트 추가
- 세션 길어지면: 핵심 요약을 `memory/YYYY-MM-DD.md`에 기록
