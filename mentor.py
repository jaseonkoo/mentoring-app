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

# [3] 🔥 [초정밀/최강력] 제목 강제 노출 및 시스템 잔상 제거 CSS
style_css = """
    <style>
    /* 기본 입력창 간격 확보 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 15px !important;
    }

    /* 📱 모바일(768px 이하)에서 제목을 강제로 띄우는 핵(Hack) */
    @media (max-width: 768px) {
        /* 1. 익스팬더 제목(p 태그)을 절대 숨기지 못하게 강제 설정 */
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            visibility: visible !important;
            position: relative !important;
            z-index: 999 !important;
            font-size: 16px !important;
            font-weight: bold !important;
            color: #31333F !important;
            line-height: 1.5 !important;
            margin: 0 !important;
            opacity: 1 !important;
        }

        /* 2. 겹침의 주범인 시스템 잔상(_arr, _down)을 완전히 투명화 및 무력화 */
        div[data-testid="stExpander"] details summary span {
            font-size: 0 !important;
            width: 0 !important;
            height: 0 !important;
            display: none !important;
            visibility: hidden !important;
        }
        
        /* 3. 제목이 들어가는 배경 박스를 보기 좋게 조정 */
        div[data-testid="stExpander"] details summary {
            min-height: 50px !important;
            display: flex !important;
            align-items: center !important;
            background-color: #f9f9f9 !important;
            border-radius: 5px !important;
            padding: 5px 10px !important;
        }

        /* 4. 탭 메뉴 글자 겹침 방지 */
        button[data-baseweb="tab"] {
            font-size: 13px !important;
            padding: 5px !important;
        }
    }
    </style>
"""
if not st.session_state.admin_logged_in:
    style_css += "<style>#MainMenu, header, footer, .stDeployButton {visibility: hidden; display:none;}</style>"
st.markdown(style_css, unsafe_allow_html=True)

st.title("🤝 DaeHanFeed Mentoring")
st.caption("대한사료 임직원 소통 플랫폼")
st.markdown("---")

# ==========================================
# ☁️ 구글 스프레드시트 연결 및 데이터 로드
# ==========================================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_gspread():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    doc = client.open("멘토링예약DB")
    ts = [w.title for w in doc.worksheets()]
    ws_s = doc.worksheet("slots") if "slots" in ts else doc.add_worksheet("slots", 1000, 20)
    ws_r = doc.worksheet("reservations") if "reservations" in ts else doc.add_worksheet("reservations", 1000, 20)
    ws_m = doc.worksheet("mentors") if "mentors" in ts else doc.add_worksheet("mentors", 100, 10)
    ws_a = doc.worksheet("admin") if "admin" in ts else doc.add_worksheet("admin", 10, 2)
    return ws_s, ws_r, ws_m, ws_a

ws_slots, ws_res, ws_mentors, ws_admin = init_gspread()

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
        for c in ['date', 'start', 'end', 'start_time', 'end_time']:
            if c in df.columns: df[c] = df[c].astype(str)
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())

if "data_loaded" not in st.session_state:
    load_data(); st.session_state.data_loaded = True

def send_email(to_email, subject, body):
    SMTP_S, SMTP_P = "smtp.dooray.com", 465
    U, P = st.secrets["email"]["smtp_user"], st.secrets["email"]["smtp_password"]
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'], msg['From'], msg['To'] = Header(subject, 'utf-8'), U, to_email
        with smtplib.SMTP_SSL(SMTP_S, SMTP_P) as server:
            server.login(U, P)
            server.sendmail(U, to_email, msg.as_string())
        st.toast("✅ 메일 전송 완료")
    except: pass

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성 (Tab 1 ~ Tab 4)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약", "💼 내 일정", "📋 신청 현황", "👑 관리자"])

# --- [Tab 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 예약 가능 현황 확인", expanded=True):
        if not st.session_state.available_slots: st.info("일정이 없습니다.")
        else:
            summ = {}
            for s in st.session_state.available_slots:
                booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not booked:
                    info = f"{s['date'].strftime('%m/%d')} ({s['start'].strftime('%H:%M')} ~ {s['end'].strftime('%H:%M')})"
                    summ[s['mentor']] = summ.get(s['mentor'], set()) | {info}
            for m, infos in summ.items():
                st.success(f"✅ **{m}** : {', '.join(sorted(list(infos)))}")

    c1, c2 = st.columns(2)
    name = c1.text_input("성함", key="m_name_t1")
    email = c2.text_input("이메일", key="m_email_t1")
    sel_m = st.selectbox("멘토 선택", mentor_names, key="m_sel_t1")
    sel_d = st.date_input("날짜", datetime.date.today() + datetime.timedelta(days=1), key="d_sel_t1")
    
    slots = [s for s in st.session_state.available_slots if s['mentor']==sel_m and s['date']==sel_d]
    if slots:
        st.info(f"📍 {slots[0].get('location','-')} | ⏰ {slots[0]['start']} ~ {slots[0]['end']}")
        topic = st.text_area("주제 (필수)", key="topic_t1")
        if st.button("🚀 신청하기", type="primary", use_container_width=True, key="btn_t1"):
            res = {"id": str(uuid.uuid4()), "mentor": sel_m, "mentee_name": name, "mentee_email": email, "date": sel_d, "start_time": slots[0]['start'], "end_time": slots[0]['end'], "topic": topic, "location": slots[0].get('location',''), "status": "대기중"}
            st.session_state.reservations.append(res); safe_save(ws_res, st.session_state.reservations); st.balloons(); st.rerun()

# --- [Tab 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 나의 일정 등록")
    m_login = st.selectbox("성함 선택", mentor_names, key="m_login_t2")
    if m_login != "선택해주세요":
        minfo = next((m for m in st.session_state.mentors_data if m['name']==m_login), None)
        if minfo and st.text_input("비밀번호", type="password", key="m_pw_t2") == str(minfo['pw']):
            c2_1, c2_2, c2_3, c2_4 = st.columns(4)
            d_v, s_v, e_v, l_v = c2_1.date_input("날짜", key="s_d"), c2_2.time_input("시작", key="s_s"), c2_3.time_input("종료", key="s_e"), c2_4.text_input("장소", key="s_l")
            if st.button("일정 등록", key="s_btn"):
                st.session_state.available_slots.append({"mentor": m_login, "date": d_v, "start": s_v, "end": e_v, "location": l_v})
                safe_save(ws_slots, st.session_state.available_slots); st.rerun()

# --- [Tab 3: 예약 현황 관리] ---
with tab3:
    st.subheader("📋 멘티 신청 관리")
    m_sel3 = st.selectbox("성함 선택", mentor_names, key="m_sel_t3")
    if m_sel3 != "선택해주세요":
        minfo3 = next((m for m in st.session_state.mentors_data if m['name']==m_sel3), None)
        if minfo3 and st.text_input("비번 확인", type="password", key="m_pw_t3") == str(minfo3['pw']):
            for r in [x for x in st.session_state.reservations if x['mentor']==m_sel3]:
                with st.expander(f"[{r['status']}] {r['date']} | {r['mentee_name']}님"):
                    st.write(f"주제: {r['topic']}")
                    if r['status'] == "대기중" and st.button("✅ 승인", key=f"ok_{r['id']}"):
                        r['status']="승인됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [Tab 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 관리자 메뉴")
    if not st.session_state.admin_logged_in:
        a_id = st.text_input("Admin ID", key="ad_id")
        a_pw = st.text_input("Admin PW", type="password", key="ad_pw")
        if st.button("로그인", key="ad_btn"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃", key="ad_out"): st.session_state.admin_logged_in = False; st.rerun()
        
        # [신규 등록] 3단 레이아웃
        with st.expander("👨‍🏫 멘토 신규 등록", expanded=False):
            r1_1, r1_2, r1_3, r1_4 = st.columns(4)
            nm, np, nt, n_pw = r1_1.text_input("성함", key="n_nm"), r1_2.text_input("직급", key="n_np"), r1_3.text_input("팀명", key="n_nt"), r1_4.text_input("비번", key="n_pw")
            r2_1, r2_2 = st.columns([1.5, 2.5])
            ne, nex = r2_1.text_input("이메일", key="n_ne"), r2_2.text_input("전문분야", key="n_nx")
            ng = st.text_area("인사말", key="n_ng")
            if st.button("등록", key="n_btn"):
                st.session_state.mentors_data.append({"name":nm, "position":np, "team":nt, "pw":n_pw, "expertise":nex, "greeting":ng, "email":ne})
                safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()

        # [수정/삭제] 3단 레이아웃
        with st.expander("📋 멘토 수정/삭제", expanded=True):
            for i, m in enumerate(st.session_state.mentors_data):
                st.write(f"**{m['name']} 멘토**")
                er1, er2, er3, er4 = st.columns(4)
                un, up, ut, upw = er1.text_input("성함", m['name'], key=f"un_{i}"), er2.text_input("직급", m.get('position',''), key=f"up_{i}"), er3.text_input("팀명", m.get('team',''), key=f"ut_{i}"), er4.text_input("비번", m.get('pw',''), key=f"upw_{i}")
                er2_1, er2_2 = st.columns([1.5, 2.5])
                uem, uex = er2_1.text_input("이메일", m.get('email',''), key=f"ue_{i}"), er2_2.text_input("전문분야", m.get('expertise',''), key=f"ux_{i}")
                ug = st.text_area("인사말", m.get('greeting',''), key=f"ug_{i}")
                if st.button("💾 저장", key=f"sv_{i}"):
                    st.session_state.mentors_data[i].update({"name":un, "position":up, "team":ut, "pw":upw, "email":uem, "expertise":uex, "greeting":ug})
                    safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                if st.button("❌ 삭제", key=f"dl_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                st.divider()
