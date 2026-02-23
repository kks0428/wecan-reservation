# Penguin Analysis Playbook

1. 현재 시황 체크
   - `python3 active/market-monitor/penguin_monitor.py --once`
2. 상위 지갑 흐름(단기)
   - Top20/Top100 순유입·순유출 체크
3. 의심 지갑 딥다이브
   - counterpart(유입/유출 상대) 추적
4. 결과 저장
   - 리포트는 `state/`에 저장
