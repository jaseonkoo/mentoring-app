import streamlit as st
import datetime
import uuid
import pandas as pd
import gspread
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from oauth2client.service_account import ServiceAccountCredentials

# [1] 브라우저 및 페이지 기본 설정
st.set_page_config(page_title="DaeHanFeed Mentoring", page_icon="🤝", layout="wide")

# 시스템 접속 주소
SYSTEM_URL = "https://share.streamlit.io/jaseonkoo/mentoring-app/main/mentor.py"

# [2] 세션 상태 초기화
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# [3] 🛠️ [정밀 교정] 제목은 살리고 겹침만 방지하는 CSS
style_css = """
    <style>
    /* 1. 기본 간격 확보 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 15px !important;
    }

    /* 2. 📱 모바일(768px 이하) 정밀 디자인 */
    @media (max-width: 768px) {
        /* 제목 글자가 사라지지 않도록 명시적으로 표시 */
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            visibility: visible !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            line-height: 1.6 !important;
            margin: 0 !important;
            color: #31333F !important; /* 스트림릿 기본 텍스트 색상 */
        }
        
        /* 시스템 잔상(_arr, _down)이 있는 span 태그만 투명하게 처리 (공간은 유지하되 글자만 안보이게) */
        div[data-testid="stExpander"] details summary span {
            font-size: 0 !important;
            color: transparent !important;
        }

        /* 탭 메뉴 겹침 방지 */
        button[data-baseweb="tab"] {
            font-size: 14px !important;
            padding: 8px !important;
        }

        /* 전체 행간 확보 */
        div[data-testid="stMarkdownContainer"] p {
            line-height: 1.7 !important;
        }
    }

    /* 관리자 메뉴 제어 */
"""
if not st.session_state.admin_logged_in:
    style_css += """
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    """
style_css += "</style>"
st.markdown(style_css, unsafe_allow_html=True)

st.title("🤝 DaeHanFeed Mentoring")
st.caption("대한사료 임직원 간의 성장을 돕는 실시간 소통 플랫폼")
st.markdown("---")

# ==========================================
# ☁️ 구글 스프레드시트 연결 설정
# ==========================================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_gspread():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    doc = client.open("멘토링예약DB")
    
    titles = [w.title for w in doc.worksheets()]
    ws_slots = doc.worksheet("slots") if "slots" in titles else doc.add_worksheet("slots", 1000, 20)
    ws_res = doc.worksheet("reservations") if "reservations" in titles else doc.add_worksheet("reservations", 1000, 20)
    ws_mentors = doc.worksheet("mentors") if "mentors" in titles else doc.add_worksheet("mentors", 100, 10)
    ws_admin = doc.worksheet("admin") if "admin" in titles else doc.add_worksheet("admin", 10, 2)
    
    return ws_slots, ws_res, ws_mentors, ws_admin

ws_slots, ws_res, ws_mentors, ws_admin = init_gspread()

# ==========================================
# 💾 데이터 처리 함수
# ==========================================
def load_data():
    try: st.session_state.admin_info = ws_admin.get_all_records()[0]
    except: st.session_state.admin_info = {"id": "admin", "pw": "dhfeed1947"}
    st.session_state.mentors_data = ws_mentors.get_all_records()
    
    slots = ws_slots.get_all_records()
    for s in slots:
        s['date'] = datetime.datetime.strptime(str(s['date']), "%Y-%m-%d").date()
        s['start'] = datetime.datetime.strptime(str(s['start']), "%H:%M:%S").time()
        s['end'] = datetime.datetime.strptime(str(s['end']), "%H:%M:%S").time()
    st.session_state.available_slots = slots
    
    res = ws_res.get_all_records()
    for r in res:
        r['date'] = datetime.datetime.strptime(str(r['date']), "%Y-%m-%d").date()
        r['start_time'] = datetime.datetime.strptime(str(r['start_time']), "%H:%M:%S").time()
        r['end_time'] = datetime.datetime.strptime(str(r['end_time']), "%H:%M:%S").time()
    st.session_state.reservations = res

def safe_save(ws, data_list):
    ws.clear()
    if data_list:
        df = pd.DataFrame(data_list)
        for col in ['date', 'start', 'end', 'start_time', 'end_time']:
            if col in df.columns: df[col] = df[col].astype(str)
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())

if "data_loaded" not in st.session_state:
    load_data()
    st.session_state.data_loaded = True

# ==========================================
# 📊 탭 구성 및 메인 로직
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 실시간 예약 가능 현황 확인하기", expanded=True):
        if not st.session_state.available_slots:
            st.info("현재 등록된 일정이 없습니다.")
        else:
            avail_summary = {}
            for s in st.session_state.available_slots:
                is_booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not is_booked:
                    time_info = f"{s['date'].strftime('%m/%d')} ({s['start'].strftime('%H:%M')}~{s['end'].strftime('%H:%M')})"
                    avail_summary[s['mentor']] = avail_summary.get(s['mentor'], set()) | {time_info}
            
            if not avail_summary: st.write("모든 일정이 마감되었습니다.")
            else:
                for m, infos in avail_summary.items():
                    st.success(f"✅ **{m}** : {', '.join(sorted(list(infos)))}")

    st.markdown("---")
    mentee_name = st.text_input("신청자 성함")
    mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]
    selected_m = st.selectbox("상담받을 멘토 선택", mentor_names)
    # ... (이후 기존의 예약 신청 로직 유지)
