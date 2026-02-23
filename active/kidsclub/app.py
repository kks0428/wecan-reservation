import html
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# =========================
# 기본 설정
# =========================
st.set_page_config(page_title="키즈클럽 예약 조회", page_icon="📅", layout="centered")

st.markdown(
    """
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 720px;}
.k-card {
  border: 1px solid #E5E7EB;
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 10px;
  background: #FFFFFF !important;
  color: #111827 !important;
}
.k-date {font-weight: 700; font-size: 1rem; color:#111827 !important;}
.k-total {color: #B91C1C !important; font-weight: 700;}
.k-slot {
  margin-top: 8px;
  padding: 8px;
  border-radius: 10px;
  background: #F9FAFB !important;
  color:#111827 !important;
  border:1px solid #E5E7EB;
}
.k-slot-title {font-weight: 600; margin-bottom: 4px; color:#111827 !important;}
.k-empty {color: #6B7280 !important;}
.badge {
  display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px;
  border:1px solid #FECACA; background:#FEF2F2 !important; color:#B91C1C !important; font-weight:600;
}
.friend-name {
  background:#FEF3C7;
  color:#92400E !important;
  border:1px solid #F59E0B;
  border-radius:8px;
  padding:1px 6px;
  font-weight:700;
  display:inline-block;
}
.child-name {
  background:#DBEAFE;
  color:#1E3A8A !important;
  border:1px solid #3B82F6;
  border-radius:8px;
  padding:1px 6px;
  font-weight:800;
  display:inline-block;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("📅 키즈클럽 예약 조회")
st.caption("오늘 기준 +30일 범위만 조회됩니다.")

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

FALLBACK_ID = "하연01"
FALLBACK_PW = "2677"
DEFAULT_FRIENDS = ["채원01", "호연01", "예나01", "보아02"]
CHILD_NAME = "하연01"


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
            login_url = "https://wecankidsclub.younmanager.com/bbs/login_check.php"
            data = {
                "mb_id": self.user_id,
                "mb_password": self.user_pw,
                "url": "https://wecankidsclub.younmanager.com/",
            }
            res = self.session.post(login_url, data=data, headers=self.headers, timeout=12)
            res.raise_for_status()
            if "비밀번호가 틀립니다" in res.text or "존재하지 않는 회원" in res.text:
                return False, "아이디 또는 비밀번호가 틀렸습니다."
            return True, "로그인 성공"
        except requests.RequestException as e:
            return False, f"로그인 요청 실패: {e}"
        except Exception as e:
            return False, f"로그인 오류: {e}"

    def get_rolling_30d_data(self, watch_names=None):
        watch_names = watch_names or []
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=30)

        rows = []
        friend_hits = []
        errors = []

        # 대략 진행률 계산용
        total_steps = 0
        d = start_date
        while d <= end_date:
            total_steps += len(DAY_SCHEDULE_MAP[d.weekday()]) or 1
            d += timedelta(days=1)

        progress = st.progress(0)
        progress_text = st.empty()
        step = 0

        d = start_date
        while d <= end_date:
            date_str = d.strftime("%Y-%m-%d")
            weekday_num = d.weekday()
            day_name = ["월", "화", "수", "목", "금", "토", "일"][weekday_num]

            row = {
                "날짜": date_str,
                "요일": day_name,
                "총인원": 0,
                "is_closed": False,
                "slots": {},
            }

            current_map = DAY_SCHEDULE_MAP[weekday_num]
            if not current_map:
                row["is_closed"] = True
                rows.append(row)
                step += 1
                progress.progress(min(step / total_steps, 1.0))
                progress_text.text(f"조회 중... {date_str}")
                d += timedelta(days=1)
                continue

            for _, label in current_map.items():
                row["slots"][label] = []

            for k, label in current_map.items():
                try:
                    params = {"bo_table": "res", "select": date_str, "k": k}
                    res = self.session.get(
                        "https://wecankidsclub.younmanager.com/theme/rs/skin/board/rs/write_res_list_get.php",
                        params=params,
                        headers=self.headers,
                        timeout=10,
                    )
                    res.raise_for_status()

                    raw_text = BeautifulSoup(res.text, "html.parser").get_text(strip=True)
                    if raw_text and "아직 예약자가 없습니다" not in raw_text:
                        names = [n.strip() for n in raw_text.split(",") if n.strip()]
                        row["slots"][label] = names
                        row["총인원"] += len(names)

                        lower_names = [n.lower() for n in names]
                        for wn in watch_names:
                            if wn and wn.lower() in lower_names:
                                friend_hits.append((date_str, label, wn))

                except Exception as e:
                    errors.append(f"{date_str} {label}: {e}")

                step += 1
                progress.progress(min(step / total_steps, 1.0))
                progress_text.text(f"조회 중... {date_str}")

            rows.append(row)
            d += timedelta(days=1)

        progress.empty()
        progress_text.empty()

        return rows, friend_hits, errors


with st.sidebar:
    st.header("🔐 로그인")
    try:
        default_id = st.secrets.get("USER_ID", FALLBACK_ID)
        default_pw = st.secrets.get("USER_PW", FALLBACK_PW)
    except Exception:
        default_id = FALLBACK_ID
        default_pw = FALLBACK_PW

    user_id = st.text_input("아이디", value=default_id)
    user_pw = st.text_input("비밀번호", value=default_pw, type="password")

    st.divider()
    st.header("🔔 친구 감지")
    use_friend_alert = st.checkbox("친구 감지 켜기", value=True)
    watch_raw = st.text_area("감지 이름(쉼표 구분)", value=", ".join(DEFAULT_FRIENDS), height=90)

    st.divider()
    only_with_reservation = st.checkbox("예약 있는 날짜만 보기", value=True)
    only_friend_days = st.checkbox("친구 있는 날짜만 보기", value=False)

watch_names = [x.strip() for x in watch_raw.split(",") if x.strip()]

if st.button("🚀 오늘+30일 조회", type="primary", use_container_width=True):
    if not user_id or not user_pw:
        st.warning("아이디/비밀번호를 입력해줘.")
    else:
        checker = ReservationChecker(user_id, user_pw)
        with st.spinner("로그인 중..."):
            ok, msg = checker.login()

        if not ok:
            st.error(msg)
        else:
            rows, hits, errors = checker.get_rolling_30d_data(watch_names if use_friend_alert else [])

            hit_set = {(d, t, n) for d, t, n in hits}
            hit_dates = {d for d, _, _ in hit_set}

            if use_friend_alert:
                if hit_set:
                    st.error(f"🚨 친구 예약 감지 {len(hit_set)}건")
                    for d, t, n in sorted(hit_set):
                        st.write(f"- **{d} {t}** → `{n}`")
                else:
                    st.info("친구 예약 감지 없음")

            total_people = sum(r["총인원"] for r in rows)
            active_days = sum(1 for r in rows if r["총인원"] > 0)
            st.success(f"조회 완료: 총 {len(rows)}일 / 예약 있는 날 {active_days}일 / 총 인원 {total_people}명")

            filtered = []
            for r in rows:
                if only_with_reservation and r["총인원"] == 0:
                    continue
                if only_friend_days and r["날짜"] not in hit_dates:
                    continue
                filtered.append(r)

            if not filtered:
                st.info("조건에 맞는 데이터가 없어.")
            else:
                for r in filtered:
                    date_label = f"{r['날짜']} ({r['요일']})"
                    badge = " <span class='badge'>친구 있음</span>" if r["날짜"] in hit_dates else ""
                    st.markdown(
                        f"<div class='k-card'><div class='k-date'>{date_label}{badge}</div><div class='k-total'>총인원 {r['총인원']}명</div></div>",
                        unsafe_allow_html=True,
                    )

                    if r["is_closed"]:
                        st.caption("휴무")
                        continue

                    for slot in TIME_COLUMNS:
                        if slot not in r["slots"]:
                            continue
                        names = r["slots"].get(slot, [])
                        if not names:
                            continue
                        rendered_names = []
                        watch_lower = {w.lower() for w in watch_names}
                        child_lower = CHILD_NAME.lower()
                        for nm in names:
                            esc = html.escape(nm)
                            nml = nm.lower()
                            if nml == child_lower:
                                rendered_names.append(f"<span class='child-name'>{esc}</span>")
                            elif nml in watch_lower:
                                rendered_names.append(f"<span class='friend-name'>{esc}</span>")
                            else:
                                rendered_names.append(esc)
                        safe = ", ".join(rendered_names)
                        st.markdown(
                            f"<div class='k-slot'><div class='k-slot-title'>{slot}</div><div>{safe}</div></div>",
                            unsafe_allow_html=True,
                        )

            if errors:
                with st.expander(f"⚠️ 조회 오류 {len(errors)}건"):
                    for e in errors[:80]:
                        st.write("-", e)
