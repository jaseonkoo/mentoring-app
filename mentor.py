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

# 시스템 접속 주소 (메일 알림용)
SYSTEM_URL = "https://share.streamlit.io/jaseonkoo/mentoring-app/main/mentor.py"

# [2] 세션 상태 초기화
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# [3] ✨ 모바일 겹침 완벽 해결을 위한 정밀 CSS
style_css = """
    <style>
    /* 1. 기본 입력창 간격 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 10px !important;
    }

    /* 2. 모바일 반응형 대응 (화면 너비 768px 이하) */
    @media (max-width: 768px) {
        /* 익스팬더(Expander) 헤더 겹침 해결 */
        div[data-testid="stExpander"] details summary {
            display: flex !important;
            align-items: center !important;
            padding: 10px !important;
            line-height: 1.4 !important;
        }

        /* 내부의 불필요한 화살표 라벨 텍스트(_arrow 등) 숨기기 */
        div[data-testid="stExpander"] details summary span:empty {
            display: none !important;
        }

        /* 텍스트 줄바꿈 및 간격 최적화 */
        div[data-testid="stMarkdownContainer"] p {
            line-height: 1.6 !important;
            font-size: 15px !important;
            white-space: normal !important;
            margin-bottom: 5px !important;
        }
        
        /* 제목 글자 크기 조절 */
        h1 { font-size: 22px !important; }
        h2 { font-size: 18px !important; }
        h3 { font-size: 16px !important; }
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

# ==========================================
# 📧 [실전] Dooray! SMTP 이메일 발송 함수
# ==========================================
def send_email(to_email, subject, body):
    SMTP_SERVER = "smtp.dooray.com"
    SMTP_PORT = 465 
    SMTP_USER = st.secrets["email"]["smtp_user"]
    SMTP_PW = st.secrets["email"]["smtp_password"]
    
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PW)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        st.toast(f"✅ 메일 발송 완료", icon="📧")
    except Exception as e:
        st.error(f"❌ 메일 발송 오류")

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 예약 가능 날짜 확인", expanded=True):
        if not st.session_state.available_slots:
            st.info("현재 등록된 멘토링 일정이 없습니다.")
        else:
            avail_summary = {}
            for s in st.session_state.available_slots:
                is_booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not is_booked:
                    d_str = s['date'].strftime("%m/%d")
                    avail_summary[s['mentor']] = avail_summary.get(s['mentor'], set()) | {d_str}
            if not avail_summary: st.write("모든 일정이 마감되었습니다.")
            else:
                for m, dates in avail_summary.items():
                    st.success(f"✅ **{m}** : {', '.join(sorted(list(dates)))}")

    st.markdown("---")
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        mentee_name = st.text_input("성함")
        mentee_pos = st.text_input("직급")
    with col_info2:
        mentee_team = st.text_input("팀명")
        mentee_email = st.text_input("이메일")

    t_start = t_end = None
    sel_location = "" 
    col_main, col_profile = st.columns([1.2, 1])

    with col_main:
        selected_m = st.selectbox("멘토 선택", mentor_names)
        sel_date = st.date_input("날짜 선택", datetime.date.today() + datetime.timedelta(days=1))
        slots_found = [s for s in st.session_state.available_slots if s['mentor']==selected_m and s['date']==sel_date]
        if slots_found:
            for s in slots_found:
                st.info(f"📍 {s.get('location', '장소 미지정')} | ⏰ {s['start'].strftime('%H:%M')} ~ {s['end'].strftime('%H:%M')}")
                sel_location = s.get('location', '')
            cs, ce = st.columns(2)
            with cs: t_start = st.time_input("시작", slots_found[0]['start'])
            with ce: t_end = st.time_input("종료", slots_found[0]['end'])
        elif selected_m != "선택해주세요":
            st.warning("일정이 없습니다.")
        
        m_topic = st.text_area("상담 주제 (필수)")

    with col_profile:
        if selected_m != "선택해주세요":
            p_card = next((m for m in st.session_state.mentors_data if m['name'] == selected_m), None)
            if p_card:
                st.info(f"🎖️ {p_card['name']} {p_card.get('position','')} 멘토\n\n🏢 {p_card.get('team','')}\n🎯 {p_card.get('expertise','')}")

    if st.button("🚀 신청하기", type="primary", use_container_width=True):
        if not mentee_name or selected_m == "선택해주세요" or not m_topic:
            st.error("필수 항목을 입력하세요.")
        else:
            new_res = {"id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": mentee_name, "mentee_position": mentee_pos, "mentee_team": mentee_team, "mentee_email": mentee_email, "date": sel_date, "start_time": t_start, "end_time": t_end, "topic": m_topic, "location": sel_location, "status": "대기중"}
            st.session_state.reservations.append(new_res)
            safe_save(ws_res, st.session_state.reservations)
            st.success("신청 완료!"); st.rerun()

# --- [💼 탭 2/3/4 는 동일하므로 생략하지 않고 핵심 디자인만 유지] ---
# ... (이후 탭 2, 3, 4의 기존 로직을 그대로 유지하되, 전체 코드가 필요하시니 아래에 모두 담습니다)

# 💼 탭 2: 멘토 일정 관리
with tab2:
    st.subheader("💼 나의 일정 관리")
    m_login = st.selectbox("성함 선택", mentor_names, key="m_login_t2")
    if m_login != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_login), None)
        if m_info and st.text_input("비번", type="password", key="m_pw_t2") == str(m_info['pw']):
            c1, c2, c3, c4 = st.columns(4)
            d_val = c1.date_input("날짜", key="d_t2")
            s_val = c2.time_input("시작", key="s_t2")
            e_val = c3.time_input("종료", key="e_t2")
            loc_val = c4.text_input("장소", key="l_t2")
            if st.button("등록"):
                st.session_state.available_slots.append({"mentor": m_login, "date": d_val, "start": s_val, "end": e_val, "location": loc_val})
                safe_save(ws_slots, st.session_state.available_slots); st.rerun()

# 📋 탭 3: 예약 관리
with tab3:
    st.subheader("📋 신청 현황")
    m_sel_t3 = st.selectbox("성함 선택", mentor_names, key="m_sel_t3")
    if m_sel_t3 != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_sel_t3), None)
        if m_info and st.text_input("비번 확인", type="password", key="pw_t3") == str(m_info['pw']):
            for r in [res for res in st.session_state.reservations if res['mentor']==m_sel_t3]:
                with st.expander(f"{r['date']} | {r['mentee_name']}님 ({r['status']})"):
                    st.write(f"주제: {r['topic']}")
                    if r['status'] == "대기중":
                        if st.button("✅ 승인", key=f"ok_{r['id']}"):
                            r['status'] = "승인됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()
                        if st.button("❌ 거절", key=f"no_{r['id']}"):
                            r['status'] = "거절됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# 👑 탭 4: 관리자
with tab4:
    st.subheader("👑 관리자 전용")
    if not st.session_state.admin_logged_in:
        a_id, a_pw = st.text_input("ID"), st.text_input("PW", type="password")
        if st.button("로그인"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        with st.expander("👨‍🏫 멘토 등록"):
            nc1, nc2 = st.columns(2)
            n_m = nc1.text_input("성함", key="nm")
            n_pw = nc2.text_input("비번", key="npw")
            if st.button("등록하기"):
                st.session_state.mentors_data.append({"name":n_m, "pw":n_pw})
                safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
        with st.expander("📋 멘토 관리"):
            for i, m in enumerate(st.session_state.mentors_data):
                st.write(f"**{m['name']}**")
                if st.button("❌ 삭제", key=f"del_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
