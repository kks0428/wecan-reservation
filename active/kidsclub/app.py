import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import calendar
import html

# =========================
# 기본 설정
# =========================
st.set_page_config(page_title="월간 예약 조회", page_icon="📅", layout="wide")

st.markdown(
    """
<style>
.stDataFrame { font-size: 14px; }
[data-testid="stSidebar"] { min-width: 220px; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("📅 키즈클럽 월간 예약 현황")
st.caption("좌측 사이드바에서 설정 후 '월간 전체 조회' 버튼을 누르세요.")

TIME_COLUMNS = ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
DAY_SCHEDULE_MAP = {
    0: {},  # 월 휴무
    1: {2: "5~6시", 3: "6~7시"},
    2: {4: "3~4시", 1: "4~5시", 2: "5~6시"},
    3: {1: "4~5시", 2: "5~6시", 3: "6~7시"},
    4: {1: "3~4시", 2: "4~5시", 3: "5~6시"},
    5: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"},
    6: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"},
}

# 요청하신 기본 계정값
FALLBACK_ID = "하연01"
FALLBACK_PW = "2677"

# 친구 알림 기본 목록
DEFAULT_FRIENDS = ["채원01", "호연01", "예나01", "보아02"]


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

    def get_monthly_data(self, selected_date, watch_names=None):
        watch_names = watch_names or []

        year = selected_date.year
        month = selected_date.month
        last_day = calendar.monthrange(year, month)[1]
        start_date = datetime(year, month, 1).date()

        table_data = []
        errors = []
        found_hits = []  # [(date, time_label, friend_name, all_names)]

        progress_text = st.empty()
        progress_bar = st.progress(0)

        for i in range(last_day):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            weekday_num = current_date.weekday()
            day_name = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"][weekday_num]

            progress_percent = (i + 1) / last_day
            progress_bar.progress(progress_percent)
            progress_text.text(f"{date_str} 데이터 조회 중... ({i+1}/{last_day})")

            date_html = f"<b>{date_str}</b><br><span style='color:#666; font-size:12px;'>{day_name}</span>"
            row = {"날짜": date_html, "총인원": ""}
            for col in TIME_COLUMNS:
                row[col] = "-"

            current_map = DAY_SCHEDULE_MAP[weekday_num]
            if not current_map:
                for col in TIME_COLUMNS:
                    row[col] = "<span style='color:#ff4b4b; opacity:0.5'>⛔</span>"
                table_data.append(row)
                continue

            for t_label in current_map.values():
                row[t_label] = ""

            daily_total = 0

            for k, time_label in current_map.items():
                try:
                    params = {"bo_table": "res", "select": date_str, "k": k}
                    res = self.session.get(
                        "https://wecankidsclub.younmanager.com/theme/rs/skin/board/rs/write_res_list_get.php",
                        params=params,
                        headers=self.headers,
                        timeout=10,
                    )
                    res.raise_for_status()

                    soup = BeautifulSoup(res.text, "html.parser")
                    raw_text = soup.get_text(strip=True)

                    if raw_text and "아직 예약자가 없습니다" not in raw_text:
                        names = [n.strip() for n in raw_text.split(",") if n.strip()]
                        if names:
                            daily_total += len(names)

                            # 친구 이름 탐지
                            lower_names = [n.lower() for n in names]
                            for wn in watch_names:
                                if wn and wn.lower() in lower_names:
                                    found_hits.append((date_str, time_label, wn, names))

                            safe_names = [html.escape(n) for n in names]
                            row[time_label] = ", ".join(safe_names)

                except Exception as e:
                    errors.append(f"{date_str} k={k} 오류: {e}")

            row["총인원"] = f"<b>{daily_total}명</b>" if daily_total > 0 else ""
            table_data.append(row)

        progress_bar.empty()
        progress_text.empty()

        if errors:
            with st.expander(f"⚠️ 조회 중 오류 {len(errors)}건"):
                for e in errors[:50]:
                    st.write("-", e)

        return pd.DataFrame(table_data), found_hits


# =========================
# 사이드바
# =========================
with st.sidebar:
    st.header("🔐 로그인 설정")
    try:
        default_id = st.secrets.get("USER_ID", FALLBACK_ID)
        default_pw = st.secrets.get("USER_PW", FALLBACK_PW)
    except Exception:
        default_id = FALLBACK_ID
        default_pw = FALLBACK_PW

    user_id = st.text_input("아이디", value=default_id)
    user_pw = st.text_input("비밀번호", value=default_pw, type="password")

    st.divider()
    st.header("🔔 친구 알림 설정")
    enable_friend_alert = st.checkbox("친구 예약 감지 알림 켜기", value=True)
    watch_names_raw = st.text_area(
        "감지 이름(쉼표 구분)",
        value=", ".join(DEFAULT_FRIENDS),
        help="예: 채원01, 호연01, 예나01, 보아02",
    )
    st.info("⚠️ 월간 조회는 데이터량이 많아 20~30초 정도 소요됩니다.")

watch_names = [x.strip() for x in watch_names_raw.split(",") if x.strip()]


# =========================
# 메인 UI
# =========================
col1, col2 = st.columns([1, 2])
with col1:
    target_date = st.date_input("조회할 '달'의 날짜 선택", datetime.now())
with col2:
    st.write("")
    st.write("")
    btn_run = st.button("🚀 월간 전체 조회하기", type="primary", use_container_width=True)

if btn_run:
    if not user_id or not user_pw:
        st.warning("왼쪽 사이드바에 아이디와 비밀번호를 먼저 입력해주세요.")
    else:
        checker = ReservationChecker(user_id, user_pw)

        with st.spinner("로그인 시도 중..."):
            is_login, msg = checker.login()

        if not is_login:
            st.error(msg)
        else:
            df, hits = checker.get_monthly_data(
                target_date,
                watch_names=watch_names if enable_friend_alert else [],
            )

            cols = ["날짜", "총인원", "11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
            df = df[cols]

            st.success(f"✅ {target_date.strftime('%Y년 %m월')} 예약 현황 조회 완료!")
            st.caption("↔ 표가 길면 좌우 스크롤해서 확인하세요.")

            if enable_friend_alert:
                unique_hits = {(d, t, n) for d, t, n, _ in hits}
                if unique_hits:
                    st.error(f"🚨 친구 예약 감지됨! 총 {len(unique_hits)}건")
                    for d, t, n in sorted(unique_hits):
                        st.write(f"- **{d} {t}**: `{n}` 예약")

                    # 간단한 알림음(브라우저)
                    st.markdown(
                        """
                        <script>
                        const ctx = new (window.AudioContext || window.webkitAudioContext)();
                        const o = ctx.createOscillator();
                        const g = ctx.createGain();
                        o.type = 'sine';
                        o.frequency.value = 880;
                        o.connect(g); g.connect(ctx.destination);
                        g.gain.setValueAtTime(0.0001, ctx.currentTime);
                        g.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.01);
                        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
                        o.start();
                        o.stop(ctx.currentTime + 0.36);
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("친구 예약 감지 없음")

            st.markdown(
                """
                <style>
                .table-container { overflow: auto; height: 75vh; border: 1px solid #ddd; border-radius: 8px; background-color: #ffffff !important; }
                table.custom-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; min-width: 800px; }
                table.custom-table th, table.custom-table td { color: #333333 !important; padding: 10px 8px; border-bottom: 1px solid #eee; border-right: 1px solid #eee; white-space: nowrap; vertical-align: middle; }
                table.custom-table thead th { position: sticky; top: 0; background-color: #f0f2f6 !important; color: #333333 !important; font-weight: bold; z-index: 10; border-bottom: 2px solid #ccc; text-align: center; }
                table.custom-table tbody td:first-child, table.custom-table thead th:first-child { position: sticky; left: 0; background-color: #fafafa !important; z-index: 5; border-right: 2px solid #ccc; text-align: center; min-width: 85px; }
                table.custom-table thead th:first-child { z-index: 15; background-color: #e6e9ef !important; }
                table.custom-table td:nth-child(2) { background-color: #fffbf0 !important; text-align: center; font-weight: bold; color: #d63031 !important; }
                table.custom-table td:not(:first-child):not(:nth-child(2)) { text-align: left; }
                </style>
                """,
                unsafe_allow_html=True,
            )

            html_table = df.to_html(index=False, classes="custom-table", escape=False)
            st.markdown(f'<div class="table-container">{html_table}</div>', unsafe_allow_html=True)
