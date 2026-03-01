# Kidsclub 보안 + 서버단 30분 자동갱신 설정

## 변경 요약
- 하드코딩된 ID/PW 제거 (환경변수 사용)
- 모니터가 30분마다 서버에서 갱신 후 `state/kidsclub_latest_snapshot.json` 저장
- Streamlit 앱이 서버 스냅샷을 읽어 화면 반영 (페이지를 나중에 열어도 최신값 표시)
- 상태/스냅샷 파일 권한 600 적용 시도

## 1) 환경변수 파일 생성
```bash
cd /home/kspoopoo/.openclaw/workspace/active/kidsclub
cp .env.example .env
chmod 600 .env
# .env 열어서 WECAN_USER_ID / WECAN_USER_PW 입력
```

## 2) 모니터 수동 실행 테스트 (로컬/VPS 방식)
```bash
cd /home/kspoopoo/.openclaw/workspace/active/kidsclub
set -a; source .env; set +a
python3 friend_reservation_monitor.py
```

정상 실행되면 다음 파일이 생성/갱신됨:
- `/home/kspoopoo/.openclaw/workspace/state/kidsclub_latest_snapshot.json`

## 3) Streamlit Cloud 방식 (권장)
로컬 백그라운드 대신 GitHub Actions가 30분마다 스냅샷을 갱신.

### 추가된 파일
- `.github/workflows/update-snapshot.yml`
- `update_snapshot.py`
- `data/kidsclub_latest_snapshot.json` (생성 대상)

### GitHub Secrets 설정
레포 Settings → Secrets and variables → Actions에 아래 등록:
- `WECAN_USER_ID`
- `WECAN_USER_PW`
- `WECAN_WATCH_NAMES` (예: `채원01,호연01,예나01,보아02`)
- `WECAN_CHILD_NAME` (예: `하연01`)

워크플로는 30분마다 실행되어 `data/kidsclub_latest_snapshot.json`을 커밋/푸시함.
Streamlit Cloud는 해당 파일을 읽어 화면에 반영함.

## 4) Streamlit 반영
앱 사이드바에서 `서버 30분 스냅샷 사용`을 켜면,
버튼 없이도 최신 스냅샷(`data/kidsclub_latest_snapshot.json`)을 표시함.

## 4) 권장 systemd (자동 시작)
아래는 예시(직접 적용 시 sudo 필요):

```ini
# /etc/systemd/system/kidsclub-monitor.service
[Unit]
Description=Kidsclub friend reservation monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=kspoopoo
WorkingDirectory=/home/kspoopoo/.openclaw/workspace/active/kidsclub
EnvironmentFile=/home/kspoopoo/.openclaw/workspace/active/kidsclub/.env
ExecStart=/usr/bin/python3 /home/kspoopoo/.openclaw/workspace/active/kidsclub/friend_reservation_monitor.py
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/kspoopoo/.openclaw/workspace/state

[Install]
WantedBy=multi-user.target
```

적용:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kidsclub-monitor.service
sudo systemctl status kidsclub-monitor.service
```

## 보안 체크포인트
- `.env` 권한은 반드시 `600`
- 토큰 파일 권한도 `600`
- 코드/로그에 비밀번호 출력 금지
