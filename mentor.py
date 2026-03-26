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

# [3] 🔥 [최강력] 제목 강제 노출 및 겹침 방지 CSS
style_css = """
    <style>
    /* 기본 입력창 간격 확보 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 15px !important;
    }

    /* 📱 모바일(768px 이하) 전용 초강력 레이아웃 교정 */
    @media (max-width: 768px) {
        /* 1. 익스팬더 제목(p)을 무조건 화면에 띄웁니다 */
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            font-size: 16px !important;
            font-weight: bold !important;
            color: #31333F !important;
            line-height: 1.5 !important;
            margin: 0 !important;
        }

        /* 2. 겹침의 주범인 시스템 텍스트(_arr 등)를 투명하게 숨깁니다 */
        div[data-testid="stExpander"] details summary span {
            font-size: 0 !important;
            color: transparent !important;
            display: none !important;
        }
        
        /* 3. 제목 클릭 영역을 넓게 확보합니다 */
        div[data-testid="stExpander"] details summary {
            min-height: 55px !important;
            padding: 12px !important;
            background-color: #f8f9fb !important;
            border-radius: 8px !important;
        }

        /* 4. 탭 메뉴 글자 겹침 방지 */
        button[data-baseweb="tab"] {
            font-size: 13px !important;
            padding: 8px !important;
        }
    }
    </style>
"""
if not st.session_state.admin_logged_in:
    style_css += "<style>#MainMenu, header, footer, .stDeployButton {visibility: hidden; display:none;}</style>"
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
# 💾 데이터 처리 로직
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
    load_data(); st.session_state.data_loaded = True

def send_email(to_email, subject, body):
    SMTP_SERVER, SMTP_PORT = "smtp.dooray.com", 465
    SMTP_USER, SMTP_PW = st.secrets["email"]["smtp_user"], st.secrets["email"]["smtp_password"]
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'], msg['From'], msg['To'] = Header(subject, 'utf-8'), SMTP_USER, to_email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PW)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        st.toast(f"✅ 알림 메일 발송 완료")
    except: pass

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성 (Tab 1 ~ 4)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 예약 가능 현황 확인", expanded=True):
        if not st.session_state.available_slots: st.info("일정이 없습니다.")
        else:
            avail_summary = {}
            for s in st.session_state.available_slots:
                is_booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not is_booked:
                    info = f"{s['date'].strftime('%m/%d')} ({s['start'].strftime('%H:%M')} ~ {s['end'].strftime('%H:%M')})"
                    avail_summary[s['mentor']] = avail_summary.get(s['mentor'], set()) | {info}
            for m, infos in avail_summary.items():
                st.success(f"✅ **{m}** : {', '.join(sorted(list(infos)))}")

    c_t1_1, c_t1_2 = st.columns(2)
    with c_t1_1:
        mentee_name = st.text_input("신청자 성함", key="mentee_name_t1")
        mentee_pos = st.text_input("신청자 직급", key="mentee_pos_t1")
    with c_t1_2:
        mentee_team = st.text_input("신청자 팀명", key="mentee_team_t1")
        mentee_email = st.text_input("사내 이메일 주소", key="mentee_email_t1")

    selected_m = st.selectbox("멘토 선택", mentor_names, key="mentor_sel_t1")
    sel_date = st.date_input("날짜 선택", datetime.date.today() + datetime.timedelta(days=1), key="date_sel_t1")
    
    slots = [s for s in st.session_state.available_slots if s['mentor']==selected_m and s['date']==sel_date]
    if slots:
        st.info(f"📍 {slots[0].get('location','-')} | ⏰ {slots[0]['start']} ~ {slots[0]['end']}")
        topic = st.text_area("상담 주제 (필수)", key="topic_t1")
        if st.button("🚀 예약 신청", type="primary", use_container_width=True, key="submit_t1"):
            if not mentee_name or not topic: st.error("필수 항목을 입력하세요.")
            else:
                new_res = {"id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": mentee_name, "mentee_position": mentee_pos, "mentee_team": mentee_team, "mentee_email": mentee_email, "date": sel_date, "start_time": slots[0]['start'], "end_time": slots[0]['end'], "topic": topic, "location": slots[0].get('location',''), "status": "대기중"}
                st.session_state.reservations.append(new_res); safe_save(ws_res, st.session_state.reservations); st.balloons(); st.rerun()

# --- [💼 탭 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 내 일정 관리")
    m_login_t2 = st.selectbox("본인 성함 선택", mentor_names, key="m_login_t2")
    if m_login_t2 != "선택해주세요":
        m_info_t2 = next((m for m in st.session_state.mentors_data if m['name']==m_login_t2), None)
        if m_info_t2 and st.text_input("비밀번호", type="password", key="m_pw_t2_input") == str(m_info_t2['pw']):
            c2_1, c2_2, c2_3, c2_4 = st.columns(4)
            d_v, s_v, e_v, l_v = c2_1.date_input("날짜", key="slot_d"), c2_2.time_input("시작", key="slot_s"), c2_3.time_input("종료", key="slot_e"), c2_4.text_input("장소", key="slot_l")
            if st.button("일정 등록", key="slot_submit"):
                st.session_state.available_slots.append({"mentor": m_login_t2, "date": d_v, "start": s_v, "end": e_v, "location": l_v})
                safe_save(ws_slots, st.session_state.available_slots); st.rerun()

# --- [📋 탭 3: 예약 관리] ---
with tab3:
    st.subheader("📋 예약 현황 관리")
    m_sel_t3 = st.selectbox("본인 성함 선택", mentor_names, key="m_sel_t3")
    if m_sel_t3 != "선택해주세요":
        m_info_t3 = next((m for m in st.session_state.mentors_data if m['name']==m_sel_t3), None)
        if m_info_t3 and st.text_input("비번 확인", type="password", key="m_pw_t3_input") == str(m_info_t3['pw']):
            for r in [res for res in st.session_state.reservations if res['mentor']==m_sel_t3]:
                with st.expander(f"[{r['status']}] {r['date']} | {r['mentee_name']}님"):
                    st.write(f"주제: {r['topic']}")
                    if r['status'] == "대기중":
                        if st.button("✅ 승인", key=f"ok_res_{r['id']}"):
                            r['status']="승인됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 인사총무팀 관리자 전용")
    if not st.session_state.admin_logged_in:
        a_id, a_pw = st.text_input("ID", key="ad_id"), st.text_input("PW", type="password", key="ad_pw")
        if st.button("로그인", key="ad_login"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃", key="ad_logout"): st.session_state.admin_logged_in = False; st.rerun()
        st.divider()
        
        # --- [신규 등록] ---
        with st.expander("👨‍🏫 멘토 신규 등록", expanded=False):
            r1_1, r1_2, r1_3, r1_4 = st.columns(4)
            n_m = r1_1.text_input("성함", key="n_m")
            n_p = r1_2.text_input("직급", key="n_p")
            n_t = r1_3.text_input("팀명", key="n_t")
            n_pw = r1_4.text_input("비번", key="n_pw")
            r2_1, r2_2 = st.columns([1.5, 2.5])
            n_em, n_e = r2_1.text_input("이메일", key="n_em"), r2_2.text_input("전문분야", key="n_e")
            n_g = st.text_area("인사말", key="n_g")
            if st.button("멘토 등록", key="n_btn"):
                st.session_state.mentors_data.append({"name":n_m, "position":n_p, "team":n_t, "pw":n_pw, "expertise":n_e, "greeting":n_g, "email":n_em})
                safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()

        # --- [정보 수정/삭제] ---
        with st.expander("📋 멘토 수정/삭제", expanded=True):
            for i, m in enumerate(st.session_state.mentors_data):
                st.write(f"**{m['name']} 멘토**")
                er1_1, er1_2, er1_3, er1_4 = st.columns(4)
                un, up, ut, upw = er1_1.text_input("성함", m['name'], key=f"un_{i}"), er1_2.text_input("직급", m.get('position',''), key=f"up_{i}"), er1_3.text_input("팀명", m.get('team',''), key=f"ut_{i}"), er1_4.text_input("비번", m.get('pw',''), key=f"upw_{i}")
                er2_1, er2_2 = st.columns([1.5, 2.5])
                ue, ux = er2_1.text_input("이메일", m.get('email',''), key=f"ue_{i}"), er2_2.text_input("전문분야", m.get('expertise',''), key=f"ux_{i}")
                ug = st.text_area("인사말", m.get('greeting',''), key=f"ug_{i}")
                if st.button("💾 저장", key=f"sv_{i}"):
                    st.session_state.mentors_data[i].update({"name":un, "position":up, "team":ut, "pw":upw, "email":ue, "expertise":ux, "greeting":ug})
                    safe_save(ws_mentors, st.session_state.mentors_data); st.success("수정됨"); st.rerun()
                if st.button("❌ 삭제", key=f"dl_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                st.divider()
