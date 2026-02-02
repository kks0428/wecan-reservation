import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd

# --- 페이지 기본 설정 ---
st.set_page_config(
    page_title="예약 현황 조회",
    page_icon="📅",
    layout="wide" # 표를 넓게 보여주기 위함
)

# --- 스타일링 (모바일에서 표가 잘 보이게) ---
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
    [data-testid="stSidebar"] { min-width: 200px; }
</style>
""", unsafe_allow_html=True)

st.title("📅 키즈클럽 주간 예약 현황")
st.caption("요일별 시간표가 자동 적용된 실시간 조회 시스템입니다.")

# --- 사이드바: 로그인 정보 ---
with st.sidebar:
    st.header("🔐 로그인 설정")
    # Streamlit Secrets에서 불러오거나 직접 입력
    default_id = st.secrets.get("USER_ID", "")
    default_pw = st.secrets.get("USER_PW", "")
    
    user_id = st.text_input("아이디", value=default_id)
    user_pw = st.text_input("비밀번호", value=default_pw, type="password")
    
    st.info("입력한 정보는 저장되지 않습니다.")

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

    def get_weekly_data(self, selected_date):
        start_of_week = selected_date - timedelta(days=selected_date.weekday())
        
        # 1. 컬럼 정의
        time_columns = ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
        
        # 2. 요일별 k값 매핑 (최종 수정본 적용)
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
        progress_bar = st.progress(0) # 진행률 표시

        for i in range(7):
            current_date = start_of_week + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            weekday_num = current_date.weekday()
            day_name = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"][weekday_num]
            
            # 진행률 업데이트
            progress_bar.progress((i + 1) / 7)

            row = {"날짜": f"{date_str}\n{day_name}", "총인원": 0} # 날짜 포맷
            for col in time_columns:
                row[col] = "-" # 기본값

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
                            # 모바일 가독성을 위해 줄바꿈 처리
                            row[time_label] = ", ".join(names)
                except:
                    pass
            
            row["총인원"] = f"{daily_total}명" if daily_total > 0 else ""
            table_data.append(row)
        
        progress_bar.empty() # 진행바 제거
        return pd.DataFrame(table_data)

# --- 메인 화면 UI ---
col1, col2 = st.columns([1, 2])
with col1:
    target_date = st.date_input("조회할 주간의 날짜 선택", datetime.now())

with col2:
    st.write("") # 여백
    st.write("") 
    btn_run = st.button("🚀 주간 예약 조회하기", type="primary", use_container_width=True)

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
            with st.spinner(f"데이터를 불러오고 있습니다... (약 5~10초 소요)"):
                df = checker.get_weekly_data(target_date)
                
                # 컬럼 순서 지정
                cols = ["날짜", "총인원", "11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
                df = df[cols]
                
                # 결과 출력
                st.success("조회 완료!")
                
                # [수정된 부분] 시간대 컬럼 설정을 자동 생성합니다.
                # 각 시간대 컬럼을 'large'(넓음)로 설정하여 이름이 잘리지 않게 합니다.
                time_cols_config = {
                    "날짜": st.column_config.TextColumn("날짜", width="small", pinned=True),
                    "총인원": st.column_config.TextColumn("합계", width="small"),
                }
                
                # 시간대 컬럼들(11시~7시)에 대해 일괄적으로 "large" 옵션 적용
                for t_col in ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]:
                    time_cols_config[t_col] = st.column_config.TextColumn(t_col, width="large")

                # 데이터프레임 그리기
                st.dataframe(
                    df,
                    column_config=time_cols_config, # 위에서 만든 설정 적용
                    hide_index=True,
                    use_container_width=True, # 화면 가로폭 꽉 채우기
                    height=600 # 표 높이를 좀 더 늘려줌
                )