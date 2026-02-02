import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import calendar

# --- 페이지 기본 설정 ---
st.set_page_config(
    page_title="월간 예약 조회",
    page_icon="📅",
    layout="wide"
)

# --- 스타일링 (전체 폰트 크기 등) ---
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
    [data-testid="stSidebar"] { min-width: 200px; }
</style>
""", unsafe_allow_html=True)

st.title("📅 키즈클럽 월간 예약 현황")
st.caption("좌측 사이드바에 아이디/비번 입력 후 '조회' 버튼을 누르세요.")

# --- 사이드바: 로그인 정보 ---
with st.sidebar:
    st.header("🔐 로그인 설정")
    # Streamlit Cloud의 Secrets 기능을 사용하거나 직접 입력
    default_id = st.secrets.get("USER_ID", "")
    default_pw = st.secrets.get("USER_PW", "")
    
    user_id = st.text_input("아이디", value=default_id)
    user_pw = st.text_input("비밀번호", value=default_pw, type="password")
    
    st.info("⚠️ 월간 조회는 데이터량이 많아 20~30초 정도 소요됩니다.")

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
        # 1. 해당 월의 시작일과 마지막 날 계산
        year = selected_date.year
        month = selected_date.month
        last_day = calendar.monthrange(year, month)[1]
        
        start_date = datetime(year, month, 1).date()
        total_days = last_day
        
        # 2. 표의 시간 컬럼 정의
        time_columns = ["11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
        
        # 3. [최종 확정] 요일별 k값 매핑 규칙 (0:월 ~ 6:일)
        day_schedule_map = {
            0: {}, # 월: 휴무
            1: {2: "5~6시", 3: "6~7시"}, # 화 (k=2,3)
            2: {4: "3~4시", 1: "4~5시", 2: "5~6시"}, # 수 (k=4,1,2)
            3: {1: "4~5시", 2: "5~6시", 3: "6~7시"}, # 목 (k=1,2,3)
            4: {1: "3~4시", 2: "4~5시", 3: "5~6시"}, # 금 (k=1,2,3 - 시간대 다름)
            5: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"}, # 토
            6: {1: "11~12시", 2: "12~1시", 3: "1~2시", 4: "2~3시", 5: "3~4시", 6: "4~5시"}  # 일
        }

        table_data = []
        
        # 진행률 표시
        progress_text = st.empty()
        progress_bar = st.progress(0)

        for i in range(total_days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            weekday_num = current_date.weekday()
            day_name = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"][weekday_num]
            
            # 진행바 업데이트
            progress_percent = (i + 1) / total_days
            progress_bar.progress(progress_percent)
            progress_text.text(f"{date_str} 데이터 조회 중... ({i+1}/{total_days})")

            # 날짜 포맷팅 (HTML 줄바꿈 <br> 사용)
            date_html = f"<b>{date_str}</b><br><span style='color:gray'>{day_name}</span>"

            row = {"날짜": date_html, "총인원": 0}
            for col in time_columns:
                row[col] = "-" # 기본적으로 '운영 안함' 표시

            current_map = day_schedule_map[weekday_num]

            # 월요일 등 휴무 처리
            if not current_map:
                for col in time_columns: row[col] = "<span style='color:#ff4b4b; opacity:0.5'>⛔</span>"
                table_data.append(row)
                continue

            # 운영 시간은 빈칸으로 초기화
            for t_label in current_map.values():
                row[t_label] = "" 

            daily_total = 0
            
            # 실제 데이터 조회 (k값 반복)
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
                            # 이름 사이 콤마로 연결
                            row[time_label] = ", ".join(names)
                except:
                    pass
            
            row["총인원"] = f"<b>{daily_total}명</b>" if daily_total > 0 else ""
            table_data.append(row)
        
        # 완료 후 진행바 제거
        progress_bar.empty()
        progress_text.empty()
        return pd.DataFrame(table_data)

# --- 메인 화면 UI ---
col1, col2 = st.columns([1, 2])
with col1:
    target_date = st.date_input("조회할 '달'의 날짜 선택", datetime.now())

with col2:
    st.write("") # 줄맞춤용 여백
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
            # 월간 데이터 가져오기
            df = checker.get_monthly_data(target_date)
            
            # 컬럼 순서 재배치
            cols = ["날짜", "총인원", "11~12시", "12~1시", "1~2시", "2~3시", "3~4시", "4~5시", "5~6시", "6~7시"]
            df = df[cols]
            
            st.success(f"✅ {target_date.strftime('%Y년 %m월')} 예약 현황 조회 완료!")
            
            # --- [핵심] 엑셀 틀 고정 스타일 (Sticky Header & Column) ---
            st.markdown("""
            <style>
                /* 1. 표를 감싸는 스크롤 박스 */
                .table-container {
                    overflow: auto; /* 스크롤바 자동 생성 */
                    height: 75vh;   /* 모바일 화면 높이의 75% 사용 */
                    border: 1px solid #ddd;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }

                /* 2. 표 기본 디자인 */
                table.custom-table {
                    width: 100%;
                    border-collapse: separate; /* Sticky 적용을 위해 separate 필수 */
                    border-spacing: 0;
                    font-size: 13px;
                    min-width: 800px; /* 표가 너무 찌그러지지 않게 최소 너비 확보 */
                }
                
                table.custom-table th, table.custom-table td {
                    padding: 10px 8px;
                    border-bottom: 1px solid #eee;
                    border-right: 1px solid #eee;
                    white-space: nowrap; /* 줄바꿈 방지 (이름이 길어도 한 줄로) */
                    vertical-align: middle;
                }

                /* 3. [상단 고정] 헤더 (시간대) */
                table.custom-table thead th {
                    position: sticky;
                    top: 0;
                    background-color: #f0f2f6; 
                    color: #31333F;
                    font-weight: bold;
                    z-index: 10; /* 데이터보다 위에 뜸 */
                    border-bottom: 2px solid #ccc;
                    text-align: center;
                }

                /* 4. [좌측 고정] 첫 번째 컬럼 (날짜) */
                table.custom-table tbody td:first-child, 
                table.custom-table thead th:first-child {
                    position: sticky;
                    left: 0;
                    background-color: #fafafa;
                    z-index: 5; /* 일반 데이터보다 위에, 헤더보다는 아래 */
                    border-right: 2px solid #ccc; /* 고정선 강조 */
                    text-align: center;
                    min-width: 80px;
                }

                /* 5. [좌측 상단 모서리] 날짜/시간 교차점 */
                table.custom-table thead th:first-child {
                    z-index: 15; /* 제일 위에 있어야 함 */
                    background-color: #e6e9ef;
                }

                /* 총인원 컬럼 강조 */
                table.custom-table td:nth-child(2) {
                    background-color: #fffbf0;
                    text-align: center;
                    font-weight: bold;
                    color: #d63031;
                }
                
                /* 데이터 셀 텍스트 정렬 */
                table.custom-table td:not(:first-child):not(:nth-child(2)) {
                    text-align: left;
                }
            </style>
            """, unsafe_allow_html=True)

            # HTML로 변환하여 출력 (escape=False로 HTML 태그 적용)
            html_table = df.to_html(index=False, classes='custom-table', escape=False)
            st.markdown(f'<div class="table-container">{html_table}</div>', unsafe_allow_html=True)