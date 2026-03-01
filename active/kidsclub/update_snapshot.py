#!/usr/bin/env python3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = os.getenv("WECAN_BASE_URL", "https://wecankidsclub.younmanager.com")
LOGIN_URL = f"{BASE_URL}/bbs/login_check.php"
LIST_URL = f"{BASE_URL}/theme/rs/skin/board/rs/write_res_list_get.php"

USER_ID = os.getenv("WECAN_USER_ID", "")
USER_PW = os.getenv("WECAN_USER_PW", "")
WATCH_NAMES = [x.strip() for x in os.getenv("WECAN_WATCH_NAMES", "채원01,호연01,예나01,보아02").split(",") if x.strip()]
CHILD_NAME = os.getenv("WECAN_CHILD_NAME", "하연01")
SNAPSHOT_PATH = Path(os.getenv("WECAN_SNAPSHOT_PATH", str(Path(__file__).parent / "data" / "kidsclub_latest_snapshot.json")))

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


def login(session: requests.Session):
    if not USER_ID or not USER_PW:
        raise RuntimeError("WECAN_USER_ID / WECAN_USER_PW are required")

    data = {
        "mb_id": USER_ID,
        "mb_password": USER_PW,
        "url": BASE_URL + "/",
    }
    r = session.post(LOGIN_URL, data=data, headers=HEADERS, timeout=12)
    r.raise_for_status()
    if "비밀번호가 틀립니다" in r.text or "존재하지 않는 회원" in r.text:
        raise RuntimeError("login failed")


def collect_rows(session: requests.Session):
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=30)

    rows, friend_hits, child_hits = [], [], []

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        weekday_num = current_date.weekday()
        day_name = ["월", "화", "수", "목", "금", "토", "일"][weekday_num]
        current_map = DAY_SCHEDULE_MAP[weekday_num]

        row = {"날짜": date_str, "요일": day_name, "총인원": 0, "is_closed": False, "slots": {}}

        if not current_map:
            row["is_closed"] = True
            rows.append(row)
            current_date += timedelta(days=1)
            continue

        for _, label in current_map.items():
            row["slots"][label] = []

        for k, time_label in current_map.items():
            params = {"bo_table": "res", "select": date_str, "k": k}
            r = session.get(LIST_URL, params=params, headers=HEADERS, timeout=10)
            r.raise_for_status()
            raw_text = BeautifulSoup(r.text, "html.parser").get_text(strip=True)
            if not raw_text or "아직 예약자가 없습니다" in raw_text:
                continue

            names = [n.strip() for n in raw_text.split(",") if n.strip()]
            row["slots"][time_label] = names
            row["총인원"] += len(names)

            lowers = [n.lower() for n in names]
            if CHILD_NAME and CHILD_NAME.lower() in lowers:
                child_hits.append((date_str, time_label, CHILD_NAME))
            for wn in WATCH_NAMES:
                if wn.lower() in lowers:
                    friend_hits.append((date_str, time_label, wn))

        rows.append(row)
        current_date += timedelta(days=1)

    return rows, friend_hits, child_hits


def main():
    session = requests.Session()
    login(session)
    rows, friend_hits, child_hits = collect_rows(session)

    payload = {
        "updatedAt": datetime.now().isoformat(),
        "rows": rows,
        "friend_hits": sorted(list(set(friend_hits))),
        "child_hits": sorted(list(set(child_hits))),
        "watch_names": WATCH_NAMES,
        "child_name": CHILD_NAME,
    }

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"snapshot_written={SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
