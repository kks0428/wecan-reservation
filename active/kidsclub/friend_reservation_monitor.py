#!/usr/bin/env python3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://wecankidsclub.younmanager.com"
LOGIN_URL = f"{BASE_URL}/bbs/login_check.php"
LIST_URL = f"{BASE_URL}/theme/rs/skin/board/rs/write_res_list_get.php"

USER_ID = "하연01"
USER_PW = "2677"
WATCH_NAMES = ["채원01", "호연01", "예나01", "보아02"]
POLL_SECONDS = 600  # 10분
CHAT_ID = "497612383"
TOKEN_FILE = Path("/home/kspoopoo/openclaw/secrets/telegram_main_bot_token")
STATE_PATH = Path("/home/kspoopoo/.openclaw/workspace/state/friend_reservation_state.json")

TIME_COLUMNS = ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
DAY_SCHEDULE_MAP = {
    0: {},
    1: {2: "5~6시", 3: "6~7시"},
    2: {4: "3~4시", 1: "4~5시", 2: "5~6시"},
    3: {1: "4~5시", 2: "5~6시", 3: "6~7시"},
    4: {1: "3~4시", 2: "4~5시", 3: "5~6시"},
    5: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"},
    6: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": BASE_URL + "/",
}


def load_token() -> str:
    t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not t:
        raise RuntimeError("telegram token is empty")
    return t


def send_telegram(token: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    r.raise_for_status()


def login(session: requests.Session):
    data = {
        "mb_id": USER_ID,
        "mb_password": USER_PW,
        "url": BASE_URL + "/",
    }
    r = session.post(LOGIN_URL, data=data, headers=HEADERS, timeout=12)
    r.raise_for_status()
    if "비밀번호가 틀립니다" in r.text or "존재하지 않는 회원" in r.text:
        raise RuntimeError("login failed")


def collect_rolling_30d_snapshot(session: requests.Session, watch_names):
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=30)

    snapshot = set()
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        weekday_num = current_date.weekday()
        current_map = DAY_SCHEDULE_MAP[weekday_num]
        if current_map:
            for k, time_label in current_map.items():
                params = {"bo_table": "res", "select": date_str, "k": k}
                r = session.get(LIST_URL, params=params, headers=HEADERS, timeout=10)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                raw_text = soup.get_text(strip=True)
                if not raw_text or "아직 예약자가 없습니다" in raw_text:
                    continue

                names = [n.strip() for n in raw_text.split(",") if n.strip()]
                lower = [n.lower() for n in names]
                for wn in watch_names:
                    if wn.lower() in lower:
                        snapshot.add((date_str, time_label, wn))
        current_date += timedelta(days=1)

    return snapshot


def load_state():
    if not STATE_PATH.exists():
        return {"baseline": [], "last_seen": []}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(baseline, last_seen):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(
            {
                "updatedAt": datetime.now().isoformat(),
                "baseline": sorted(list(baseline)),
                "last_seen": sorted(list(last_seen)),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main():
    token = load_token()
    session = requests.Session()

    # 최초 기준 스냅샷(이전 예약 무시)
    login(session)
    current = collect_rolling_30d_snapshot(session, WATCH_NAMES)
    state = load_state()

    if not state.get("baseline"):
        baseline = set(current)
        last_seen = set(current)
        save_state(baseline, last_seen)
        send_telegram(token, "✅ 친구 예약 모니터 시작(10분 주기). 현재 시점 이전 예약은 알림에서 제외합니다.")
    else:
        baseline = set(tuple(x) for x in state.get("baseline", []))
        last_seen = set(tuple(x) for x in state.get("last_seen", []))
        send_telegram(token, "✅ 친구 예약 모니터 재시작(10분 주기).")

    while True:
        try:
            session = requests.Session()
            login(session)
            now_snapshot = collect_rolling_30d_snapshot(session, WATCH_NAMES)

            new_hits = now_snapshot - baseline - last_seen
            if new_hits:
                lines = ["🚨 신규 친구 예약 감지"]
                for d, t, n in sorted(new_hits):
                    lines.append(f"- {d} {t}: {n}")
                send_telegram(token, "\n".join(lines))

            save_state(baseline, now_snapshot)
            last_seen = now_snapshot

        except Exception as e:
            try:
                send_telegram(token, f"⚠️ 친구 예약 모니터 오류: {e}")
            except Exception:
                pass

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
