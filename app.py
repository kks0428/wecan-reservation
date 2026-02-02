import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import calendar # 월의 마지막 날짜를 계산하기 위해 필요

# --- 페이지 기본 설정 ---
st.set_page_config(
    page_title="월간 예약 조회",
    page_icon="📅",
    layout="wide"
)

# --- 스타일링 ---
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
    [data-testid="stSidebar"] { min-width: 200px; }
</style>
""", unsafe_allow_html=True)

st.title("📅 위캔키즈클럽 월간 예약 현황")
st.caption("선택한 날짜가 포함된 '한 달 치' 데이터를 모두 가져옵니다.")

# --- 사이드바: 로그인 정보 ---
with st.sidebar:
    st.header("🔐 로그인 설정")
    default_id = st.secrets.get("USER_ID", "")
    default_pw = st.secrets.get("USER_PW", "")
    
    user_id = st.text_input("아이디", value=default_id)
    user_pw = st.text_input("비밀번호", value=default_pw, type="password")
    
    st.info("⚠️ 월간 조회는 데이터량이 많아 20~30초 정도 소요될 수 있습니다.")

# --- 예약 조회 로직 클래스 ---
class ReservationChecker:
    def __init__(self, uid, upw):
        self.user_id = uid
        self.user_pw = upw
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://wecankidsclub.younmanager.com/'
        }

    def login(self):
        try:
            login_url = "https://wecankidsclub.younmanager.com/bbs/login_check.php"
            data = {'mb_id': self.user_id, 'mb_password': self.user_pw, 'url': 'https://wecankidsclub.younmanager.com/'}
            res = self.session.post(login_url, data=data, headers=self.headers)
            
            if "비밀번호가 틀립니다" in res.text or "존재하지 않는 회원" in res.text:
                return False, "아이디 또는 비밀번호가 틀렸습니다."
            return True, "로그인 성공"
        except Exception as e:
            return False, str(e)

    def get_monthly_data(self, selected_date):
        # 1. 해당 월의 시작일(1일)과 마지막 날 계산
        year = selected_date.year
        month = selected_date.month
        last_day = calendar.monthrange(year, month)[1] # 그 달이 며칠까지 있는지 (28, 30, 31)
        
        start_date = datetime(year, month, 1).date()
        total_days = last_day
        
        # 2. 컬럼 정의
        time_columns = ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
        
        # 3. 요일별 k값 매핑 (최종 수정본)
        day_schedule_map = {
            0: {}, # 월: 휴무
            1: {2: "5~6시", 3: "6~7시"}, # 화
            2: {4: "3~4시", 1: "4~5시", 2: "5~6시"}, # 수
            3: {1: "4~5시", 2: "5~6시", 3: "6~7시"}, # 목
            4: {1: "3~4시", 2: "4~5시", 3: "5~6시"}, # 금
            5: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"}, # 토
            6: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"}  # 일
        }

        table_data = []
        
        # 진행률 표시 바 생성
        progress_text = st.empty()
        progress_bar = st.progress(0)

        # 1일부터 말일까지 반복
        for i in range(total_days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            weekday_num = current_date.weekday()
            day_name = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"][weekday_num]
            
            # 진행 상태 업데이트
            progress_percent = (i + 1) / total_days
            progress_bar.progress(progress_percent)
            progress_text.text(f"데이터 수집 중... {date_str} 읽는 중 ({i+1}/{total_days})")

            row = {"날짜": f"{date_str}\n{day_name}", "총인원": 0}
            for col in time_columns:
                row[col] = "-"

            current_map = day_schedule_map[weekday_num]

            # 휴무 처리
            if not current_map:
                for col in time_columns: row[col] = "⛔"
                table_data.append(row)
                continue

            # 운영 시간 빈칸 초기화
            for t_label in current_map.values():
                row[t_label] = "" 

            daily_total = 0
            
            # 데이터 조회
            for k, time_label in current_map.items():
                try:
                    params = {'bo_table': 'res', 'select': date_str, 'k': k}
                    res = self.session.get("https://wecankidsclub.younmanager.com/theme/rs/skin/board/rs/write_res_list_get.php", params=params, headers=self.headers)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    raw_text = soup.get_text(strip=True)
                    
                    if raw_text and "아직 예약자가 없습니다" not in raw_text:
                        names = [name.strip() for name in raw_text.split(',') if name.strip()]
                        if names:
                            daily_total += len(names)
                            row[time_label] = ", ".join(names)
                except:
                    pass
            
            row["총인원"] = f"{daily_total}명" if daily_total > 0 else ""
            table_data.append(row)
        
        progress_bar.empty()
        progress_text.empty()
        return pd.DataFrame(table_data)

# --- 메인 화면 UI ---
col1, col2 = st.columns([1, 2])
with col1:
    # 날짜를 선택하면 그 달 전체를 조회하도록 안내
    target_date = st.date_input("조회하고 싶은 '달'의 아무 날짜나 선택하세요", datetime.now())

with col2:
    st.write("") 
    st.write("") 
    btn_run = st.button("🚀 월간 전체 조회하기", type="primary", use_container_width=True)

if btn_run:
    if not user_id or not user_pw:
        st.warning("왼쪽 사이드바에 아이디와 비밀번호를 먼저 입력해주세요.")
    else:
        checker = ReservationChecker(user_id, user_pw)
        
        with st.spinner("로그인 중..."):
            is_login, msg = checker.login()
        
        if not is_login:
            st.error(msg)
        else:
            # 월간 데이터 조회 시작
            df = checker.get_monthly_data(target_date)
            
            # 컬럼 순서 지정
            cols = ["날짜", "총인원", "11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
            df = df[cols]
            
            st.success(f"{target_date.strftime('%Y년 %m월')} 예약 조회 완료!")
            
            # 컬럼 설정 (가로로 넓게 보이도록)
            time_cols_config = {
                "날짜": st.column_config.TextColumn("날짜", width="small", pinned=True),
                "총인원": st.column_config.TextColumn("합계", width="small"),
            }
            for t_col in ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]:
                time_cols_config[t_col] = st.column_config.TextColumn(t_col, width="large")

            # 결과 출력
            st.success(f"{target_date.strftime('%Y년 %m월')} 예약 조회 완료!")
            
            # [수정] HTML로 변환하여 깔끔하게 출력하기
            # 1. CSS 스타일 정의 (표 디자인)
            st.markdown("""
            <style>
                /* 표 전체 디자인 */
                table.custom-table {
                    width: auto !important; /* 화면 꽉 채우지 말고 내용만큼만 */
                    margin-left: 0;
                    border-collapse: collapse;
                    font-size: 14px;
                }
                /* 헤더 (제목) 디자인 */
                table.custom-table th {
                    background-color: #f0f2f6;
                    color: #333;
                    font-weight: bold;
                    text-align: center;
                    padding: 10px;
                    border: 1px solid #ddd;
                    white-space: nowrap; /* 제목 줄바꿈 금지 */
                }
                /* 데이터 셀 디자인 */
                table.custom-table td {
                    padding: 8px 12px;
                    border: 1px solid #ddd;
                    vertical-align: top; /* 글자를 위쪽 정렬 */
                    min-width: 80px; /* 최소 너비 확보 */
                }
                /* 첫번째 컬럼(날짜) 강조 */
                table.custom-table td:nth-child(1) {
                    font-weight: bold;
                    background-color: #fafafa;
                    white-space: nowrap; /* 날짜는 줄바꿈 안 함 */
                    text-align: center;
                }
            </style>
            """, unsafe_allow_html=True)

            # 2. 데이터프레임을 HTML로 변환
            # classes='custom-table'을 주어서 위의 CSS를 적용받게 함
            html_table = df.to_html(index=False, classes='custom-table', escape=False)
            
            # 3. 화면에 그리기
            st.markdown(html_table, unsafe_allow_html=True)