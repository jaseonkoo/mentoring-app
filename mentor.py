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

# [3] 🔥 [최종 해결] 모바일 겹침 및 시스템 글자 제거 CSS
style_css = """
    <style>
    /* 1. 입력창 사이의 간격 확보 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 20px !important;
    }

    /* 2. 📱 모바일(768px 이하) 정밀 교정 */
    @media (max-width: 768px) {
        /* [핵심] 사진속의 '_arr', '_down' 같은 시스템 텍스트를 강제로 숨깁니다 */
        div[data-testid="stExpander"] details summary span {
            display: none !important;
        }
        
        /* 익스팬더(제목창)의 텍스트만 깨끗하게 중앙 정렬하고 간격을 넓힙니다 */
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            font-size: 16px !important;
            line-height: 1.8 !important;
            padding: 10px 0 !important;
            margin: 0 !important;
            word-break: keep-all !important;
        }

        /* 탭(Tab) 메뉴 글자 크기 조절 */
        button[data-baseweb="tab"] {
            font-size: 13px !important;
            padding: 5px !important;
        }

        /* 본문 텍스트 행간 확보 */
        div[data-testid="stMarkdownContainer"] p {
            line-height: 1.7 !important;
            font-size: 15px !important;
        }
    }

    /* 관리자 로그인 전 메뉴 숨기기 */
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
# ☁️ [핵심] 구글 스프레드시트 연결 설정
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
# 💾 데이터 처리 및 저장 함수
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

def send_email(to_email, subject, body):
    SMTP_SERVER, SMTP_PORT = "smtp.dooray.com", 465
    SMTP_USER, SMTP_PW = st.secrets["email"]["smtp_user"], st.secrets["email"]["smtp_password"]
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'], msg['From'], msg['To'] = Header(subject, 'utf-8'), SMTP_USER, to_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PW)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        st.toast(f"✅ 메일 발송 완료", icon="📧")
    except Exception: pass

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 실시간 예약 가능 현황 확인", expanded=True):
        if not st.session_state.available_slots:
            st.info("현재 등록된 멘토링 일정이 없습니다.")
        else:
            avail_summary = {}
            for s in st.session_state.available_slots:
                is_booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not is_booked:
                    time_info = f"{s['date'].strftime('%m/%d')} ({s['start'].strftime('%H:%M')}~{s['end'].strftime('%H:%M')})"
                    avail_summary[s['mentor']] = avail_summary.get(s['mentor'], set()) | {time_info}
            
            if not avail_summary: st.write("현재 모든 일정이 마감되었습니다.")
            else:
                for m, infos in avail_summary.items():
                    st.success(f"✅ **{m}** : {', '.join(sorted(list(infos)))}")

    st.markdown("---")
    mentee_name = st.text_input("신청자 성함")
    mentee_email = st.text_input("사내 이메일 주소")
    selected_m = st.selectbox("상담받을 멘토 선택", mentor_names)
    sel_date = st.date_input("희망 날짜 선택", datetime.date.today() + datetime.timedelta(days=1))
    
    slots_found = [s for s in st.session_state.available_slots if s['mentor']==selected_m and s['date']==sel_date]
    if slots_found:
        st.info(f"📍 {slots_found[0].get('location','장소 미지정')} | ⏰ {slots_found[0]['start'].strftime('%H:%M')}~{slots_found[0]['end'].strftime('%H:%M')}")
        m_topic = st.text_area("상담 주제 (필수)")
        if st.button("🚀 예약 신청하기", type="primary", use_container_width=True):
            if not mentee_name or not m_topic: st.error("성함과 주제를 입력해주세요.")
            else:
                new_res = {"id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": mentee_name, "mentee_email": mentee_email, "date": sel_date, "start_time": slots_found[0]['start'], "end_time": slots_found[0]['end'], "topic": m_topic, "location": slots_found[0].get('location',''), "status": "대기중"}
                st.session_state.reservations.append(new_res); safe_save(ws_res, st.session_state.reservations)
                st.success("신청 완료!"); st.rerun()
    elif selected_m != "선택해주세요":
        st.warning("선택하신 날짜에 일정이 없습니다.")

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 관리 시스템")
    if not st.session_state.admin_logged_in:
        a_id, a_pw = st.text_input("Admin ID"), st.text_input("Admin PW", type="password")
        if st.button("관리자 로그인"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        with st.expander("👨‍🏫 멘토 관리"):
            for i, m in enumerate(st.session_state.mentors_data):
                st.write(f"**{m['name']}** ({m.get('email','')})")
                if st.button("❌ 삭제", key=f"del_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()

# [기타 탭 2, 3 로직 유지]
