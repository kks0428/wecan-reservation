import html
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="키즈클럽 예약 조회", page_icon="📅", layout="centered")

st.markdown(
    """
<style>
:root {
  --bg:#F3F6FB;
  --surface:#FFFFFF;
  --text:#0F172A;
  --muted:#64748B;
  --line:#E2E8F0;
  --friend-bg:#FEF3C7;
  --friend-fg:#92400E;
  --friend-bd:#F59E0B;
  --child-bg:#DBEAFE;
  --child-fg:#1E3A8A;
  --child-bd:#3B82F6;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
  background: linear-gradient(180deg,#EEF4FF 0%, #F8FAFC 100%) !important;
  color: var(--text) !important;
}

.block-container {max-width: 760px; padding-top: 1.6rem; padding-bottom: 2rem;}

.hero {
  background: linear-gradient(135deg,#2563EB 0%, #7C3AED 100%);
  color: #fff;
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 10px;
  box-shadow: 0 8px 20px rgba(37,99,235,.22);
}
.hero-title {font-weight: 800; font-size: 1.05rem;}
.hero-sub {font-size: .85rem; opacity: .92; margin-top: 4px;}

.k-summary {
  position: sticky; top: 8px; z-index: 40;
  background: var(--surface) !important;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 8px 10px;
  margin-bottom: 10px;
  color: var(--text) !important;
}
.k-chip {
  display:inline-block;
  padding:3px 8px;
  border-radius:999px;
  font-size:12px;
  border:1px solid var(--line);
  background:#F8FAFC;
  margin-right:6px;
}

.k-card {
  border:1px solid var(--line);
  border-radius: 14px;
  background: var(--surface) !important;
  color: var(--text) !important;
  margin-bottom: 8px;
}
.k-slot {
  margin-top:6px;
  padding:8px;
  border-radius:10px;
  border:1px solid var(--line);
  background:#F8FAFC !important;
}
.k-slot-title {font-weight:700; color:var(--text) !important; margin-bottom: 4px;}

.friend-name {
  background:var(--friend-bg);
  color:var(--friend-fg) !important;
  border:1px solid var(--friend-bd);
  border-radius:8px;
  padding:1px 6px;
  font-weight:700;
  display:inline-block;
}
.child-name {
  background:var(--child-bg);
  color:var(--child-fg) !important;
  border:1px solid var(--child-bd);
  border-radius:8px;
  padding:1px 6px;
  font-weight:800;
  display:inline-block;
}

/* Streamlit expander/dark mode 강제 가독성 */
div[data-testid="stExpander"] {
  border:1px solid var(--line);
  border-radius:12px;
  background: var(--surface) !important;
}
div[data-testid="stExpander"] * { color: var(--text) !important; }
section[data-testid="stSidebar"] * { color: var(--text) !important; }

</style>
""",
    unsafe_allow_html=True,
)

TIME_COLUMNS = ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
DAY_SCHEDULE_MAP = {
    0: {}, 1: {2: "5~6시", 3: "6~7시"}, 2: {4: "3~4시", 1: "4~5시", 2: "5~6시"},
    3: {1: "4~5시", 2: "5~6시", 3: "6~7시"}, 4: {1: "3~4시", 2: "4~5시", 3: "5~6시"},
    5: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"},
    6: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"},
}

FALLBACK_ID = ""
FALLBACK_PW = ""
DEFAULT_FRIENDS = ["채원01", "호연01", "예나01", "보아02"]
CHILD_NAME = os.getenv("WECAN_CHILD_NAME", "하연01")
SNAPSHOT_PATH = Path(os.getenv("WECAN_SNAPSHOT_PATH", str(Path(__file__).parent / "data" / "kidsclub_latest_snapshot.json")))


def load_server_snapshot(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class ReservationChecker:
    def __init__(self, uid: str, upw: str):
        self.user_id = uid
        self.user_pw = upw
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://wecankidsclub.younmanager.com/",
        }

    def login(self):
        try:
            res = self.session.post(
                "https://wecankidsclub.younmanager.com/bbs/login_check.php",
                data={"mb_id": self.user_id, "mb_password": self.user_pw, "url": "https://wecankidsclub.younmanager.com/"},
                headers=self.headers,
                timeout=12,
            )
            res.raise_for_status()
            if "비밀번호가 틀립니다" in res.text or "존재하지 않는 회원" in res.text:
                return False, "아이디 또는 비밀번호가 틀렸습니다."
            return True, "로그인 성공"
        except Exception as e:
            return False, f"로그인 오류: {e}"

    def get_rolling_30d_data(self, watch_names=None):
        watch_names = watch_names or []
        start_date, end_date = datetime.now().date(), datetime.now().date() + timedelta(days=28)

        rows, friend_hits, child_hits, errors = [], [], [], []
        total_steps, d = 0, start_date
        while d <= end_date:
            total_steps += len(DAY_SCHEDULE_MAP[d.weekday()]) or 1
            d += timedelta(days=1)

        pbar, ptxt, step = st.progress(0), st.empty(), 0
        d = start_date
        while d <= end_date:
            date_str, weekday_num = d.strftime("%Y-%m-%d"), d.weekday()
            day_name = ["월", "화", "수", "목", "금", "토", "일"][weekday_num]

            # 월요일(0)은 완전 스킵: 조회도 하지 않고 결과 행도 만들지 않음
            if weekday_num == 0:
                d += timedelta(days=1)
                continue

            row = {"날짜": date_str, "요일": day_name, "총인원": 0, "is_closed": False, "slots": {}}
            current_map = DAY_SCHEDULE_MAP[weekday_num]

            if not current_map:
                row["is_closed"] = True
                rows.append(row)
                step += 1
                pbar.progress(min(step / total_steps, 1.0))
                ptxt.text(f"조회 중... {date_str}")
                d += timedelta(days=1)
                continue

            for _, label in current_map.items():
                row["slots"][label] = []

            for k, label in current_map.items():
                try:
                    res = self.session.get(
                        "https://wecankidsclub.younmanager.com/theme/rs/skin/board/rs/write_res_list_get.php",
                        params={"bo_table": "res", "select": date_str, "k": k},
                        headers=self.headers,
                        timeout=10,
                    )
                    res.raise_for_status()
                    raw_text = BeautifulSoup(res.text, "html.parser").get_text(strip=True)
                    if raw_text and "아직 예약자가 없습니다" not in raw_text:
                        names = [n.strip() for n in raw_text.split(",") if n.strip()]
                        row["slots"][label] = names
                        row["총인원"] += len(names)

                        lowers = [n.lower() for n in names]
                        if CHILD_NAME.lower() in lowers:
                            child_hits.append((date_str, label, CHILD_NAME))
                        for wn in watch_names:
                            if wn and wn.lower() in lowers:
                                friend_hits.append((date_str, label, wn))
                except Exception as e:
                    errors.append(f"{date_str} {label}: {e}")

                step += 1
                pbar.progress(min(step / total_steps, 1.0))
                ptxt.text(f"조회 중... {date_str}")

            rows.append(row)
            d += timedelta(days=1)

        pbar.empty()
        ptxt.empty()
        return rows, friend_hits, child_hits, errors


def render_result(rows, hits, child_hits, errors, watch_names):
    hit_set = {(d, t, n) for d, t, n in hits}
    child_set = {(d, t, n) for d, t, n in child_hits}
    hit_dates = {d for d, _, _ in hit_set}
    child_dates = {d for d, _, _ in child_set}

    total_people = sum(r["총인원"] for r in rows)
    active_days = sum(1 for r in rows if r["총인원"] > 0)

    st.markdown(
        f"<div class='k-summary'>"
        f"<span class='k-chip'>예약일 {active_days}일</span>"
        f"<span class='k-chip'>총인원 {total_people}명</span>"
        f"<span class='k-chip'>친구감지 {len(hit_set)}건</span>"
        f"<span class='k-chip'>하연감지 {len(child_set)}건</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    filtered = []
    for r in rows:
        if only_with_reservation and r["총인원"] == 0:
            continue
        if only_friend_days and r["날짜"] not in hit_dates:
            continue
        if only_child_days and r["날짜"] not in child_dates:
            continue
        filtered.append(r)

    if not filtered:
        st.info("조건에 맞는 데이터가 없어.")
    else:
        watch_lower = {w.lower() for w in watch_names}
        child_lower = CHILD_NAME.lower()

        for r in filtered:
            date_label = f"{r['날짜']} ({r['요일']})"
            lead_flags = []
            if r["날짜"] in child_dates:
                lead_flags.append("👧 하연")
            if r["날짜"] in hit_dates:
                lead_flags.append("👥 친구")
            flag_text = f" | {' · '.join(lead_flags)}" if lead_flags else ""

            with st.expander(f"{date_label} · 총 {r['총인원']}명{flag_text}", expanded=False):
                if r["is_closed"]:
                    st.caption("휴무")
                    continue

                for slot in TIME_COLUMNS:
                    if slot not in r["slots"]:
                        continue
                    names = r["slots"].get(slot, [])
                    if not names:
                        continue

                    rendered = []
                    for nm in names:
                        esc = html.escape(nm)
                        low = nm.lower()
                        if low == child_lower:
                            rendered.append(f"<span class='child-name'>{esc}</span>")
                        elif low in watch_lower:
                            rendered.append(f"<span class='friend-name'>{esc}</span>")
                        else:
                            rendered.append(esc)

                    st.markdown(
                        f"<div class='k-slot'><div class='k-slot-title'>{slot}</div><div>{', '.join(rendered)}</div></div>",
                        unsafe_allow_html=True,
                    )

    if errors:
        with st.expander(f"⚠️ 조회 오류 {len(errors)}건"):
            for e in errors[:80]:
                st.write("-", e)


BUILD_MARKER = "BUILD clean/kidsclub-fix · 2026-04-05-kst-fix"

st.markdown(
    f"""
<div class='hero'>
  <div class='hero-title'>키즈클럽 스마트 조회</div>
  <div class='hero-sub'>오늘부터 28일 범위(월요일 제외) · 친구/하연 자동 하이라이트 · 모바일 최적화</div>
  <div class='hero-sub' style='margin-top:6px;font-weight:700;'>{BUILD_MARKER}</div>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("🔐 로그인")
    try:
        default_id = st.secrets.get("USER_ID", FALLBACK_ID)
        default_pw = st.secrets.get("USER_PW", FALLBACK_PW)
    except Exception:
        default_id, default_pw = FALLBACK_ID, FALLBACK_PW
    user_id = st.text_input("아이디", value=default_id)
    user_pw = st.text_input("비밀번호", value=default_pw, type="password")

    st.divider()
    st.header("🔎 감지 대상")
    use_friend_alert = st.checkbox("친구 감지 켜기", value=True)
    watch_raw = st.text_area("친구 이름(쉼표 구분)", value=", ".join(DEFAULT_FRIENDS), height=90)

    st.divider()
    st.header("📌 필터")
    only_with_reservation = st.checkbox("예약 있는 날짜만", value=True)
    only_friend_days = st.checkbox("친구 있는 날짜만", value=False)
    only_child_days = st.checkbox("하연 있는 날짜만", value=False)

    st.divider()
    st.header("⚙️ 데이터 소스")
    use_server_snapshot = st.checkbox("서버 30분 스냅샷 사용", value=True)

watch_names = [x.strip() for x in watch_raw.split(",") if x.strip()]

if use_server_snapshot:
    snap = load_server_snapshot(SNAPSHOT_PATH)
    if not snap:
        st.warning("서버 스냅샷이 아직 없어. 모니터 프로세스 실행 후 새로고침해줘.")
    else:
        updated_at = snap.get("updatedAtKst") or snap.get("updatedAt") or "unknown"
        updated_at_utc = snap.get("updatedAtUtc", "")
        if updated_at_utc:
            st.caption(f"🕒 서버 갱신 시각(KST): {updated_at} | UTC: {updated_at_utc}")
        else:
            st.caption(f"🕒 서버 갱신 시각: {updated_at}")

        rows = snap.get("rows", [])
        hits = snap.get("friend_hits", [])
        child_hits = snap.get("child_hits", [])

        # 스냅샷 신선도 체크: 오래됐거나 시작일이 오늘보다 과거면 경고
        stale = False
        try:
            now_local = datetime.now(ZoneInfo("Asia/Seoul"))
            snap_dt = datetime.fromisoformat((snap.get("updatedAtKst") or snap.get("updatedAt") or "").replace("Z", "+00:00"))
            age_hours = (now_local.replace(tzinfo=None) - snap_dt.replace(tzinfo=None)).total_seconds() / 3600.0
            if age_hours > 2.0:
                stale = True
        except Exception:
            pass

        try:
            if rows:
                first_date = datetime.strptime(rows[0].get("날짜", ""), "%Y-%m-%d").date()
                if first_date < datetime.now(ZoneInfo("Asia/Seoul")).date():
                    stale = True
        except Exception:
            pass

        if stale:
            st.warning("⚠️ 서버 스냅샷이 오래되었거나 날짜 롤링이 멈췄어. 아래 '오늘+28일 즉시 조회'로 최신값 확인해줘.")

        render_result(rows, hits, child_hits, [], watch_names if use_friend_alert else [])

if st.button("🚀 오늘+28일 즉시 조회", type="primary", use_container_width=True):
    if not user_id or not user_pw:
        st.warning("아이디/비밀번호를 입력해줘.")
    else:
        checker = ReservationChecker(user_id, user_pw)
        with st.spinner("로그인 중..."):
            ok, msg = checker.login()
        if not ok:
            st.error(msg)
        else:
            rows, hits, child_hits, errors = checker.get_rolling_30d_data(watch_names if use_friend_alert else [])
            render_result(rows, hits, child_hits, errors, watch_names)
