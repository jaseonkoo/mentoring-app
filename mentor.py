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

# [3] 🛠️ [안정화 버전] 디자인 원상복구 및 모바일 겹침 방지 CSS
style_css = """
    <style>
    /* 입력창 간격 확보 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 15px !important;
    }

    /* 📱 모바일 대응 (제목 실종 해결 및 겹침 방지) */
    @media (max-width: 768px) {
        /* 익스팬더 제목(p)을 절대 숨기지 않고 줄간격만 조정 */
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            visibility: visible !important;
            line-height: 1.6 !important;
            font-size: 15px !important;
            white-space: normal !important; /* 모바일에서 자동 줄바꿈 허용 */
        }
        
        /* 겹침을 유발하는 시스템 잔상 글자만 보이지 않게 처리 */
        div[data-testid="stExpander"] details summary span:not(:has(p)) {
            font-size: 0 !important;
            color: transparent !important;
        }

        /* 탭(Tab) 메뉴 글자 크기 최적화 */
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

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성 (Tab 1 ~ 4 완벽 복구)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 예약 가능 현황 확인", expanded=True):
        if not st.session_state.available_slots: st.info("등록된 일정이 없습니다.")
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
    name = c1.text_input("신청자 성함", key="m_name_t1")
    email = c2.text_input("사내 이메일", key="m_email_t1")
    sel_m = st.selectbox("멘토 선택", mentor_names, key="m_sel_t1")
    sel_d = st.date_input("날짜 선택", datetime.date.today() + datetime.timedelta(days=1), key="d_sel_t1")
    
    slots = [s for s in st.session_state.available_slots if s['mentor']==sel_m and s['date']==sel_d]
    if slots:
        st.info(f"📍 {slots[0].get('location','-')} | ⏰ {slots[0]['start']} ~ {slots[0]['end']}")
        topic = st.text_area("상담 주제 (필수)", key="topic_t1")
        if st.button("🚀 예약 신청하기", type="primary", use_container_width=True, key="btn_t1"):
            if not name or not topic: st.error("성함과 주제를 입력해주세요.")
            else:
                new_res = {"id": str(uuid.uuid4()), "mentor": sel_m, "mentee_name": name, "mentee_email": email, "date": sel_d, "start_time": slots[0]['start'], "end_time": slots[0]['end'], "topic": topic, "location": slots[0].get('location',''), "status": "대기중"}
                st.session_state.reservations.append(new_res); safe_save(ws_res, st.session_state.reservations); st.balloons(); st.rerun()

# --- [💼 탭 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 나의 멘토링 일정 관리")
    m_login_t2 = st.selectbox("본인 성함 선택", mentor_names, key="m_login_t2")
    if m_login_t2 != "선택해주세요":
        minfo = next((m for m in st.session_state.mentors_data if m['name']==m_login_t2), None)
        if minfo and st.text_input("비밀번호", type="password", key="m_pw_t2") == str(minfo['pw']):
            c2_1, c2_2, c2_3, c2_4 = st.columns(4)
            d_v, s_v, e_v, l_v = c2_1.date_input("날짜", key="s_d"), c2_2.time_input("시작", key="s_s"), c2_3.time_input("종료", key="s_e"), c2_4.text_input("상담 장소", key="s_l")
            if st.button("일정 등록하기", key="s_btn"):
                st.session_state.available_slots.append({"mentor": m_login_t2, "date": d_v, "start": s_v, "end": e_v, "location": l_v})
                safe_save(ws_slots, st.session_state.available_slots); st.rerun()

# --- [📋 탭 3: 멘토 예약 관리] ---
with tab3:
    st.subheader("📋 멘티 신청 현황 관리")
    m_sel_t3 = st.selectbox("본인 성함 선택", mentor_names, key="m_sel_t3")
    if m_sel_t3 != "선택해주세요":
        minfo3 = next((m for m in st.session_state.mentors_data if m['name']==m_sel_t3), None)
        if minfo3 and st.text_input("비번 확인", type="password", key="m_pw_t3") == str(minfo3['pw']):
            for r in [x for x in st.session_state.reservations if x['mentor']==m_sel_t3]:
                with st.expander(f"[{r['status']}] {r['date']} | {r['mentee_name']}님"):
                    st.write(f"주제: {r['topic']}")
                    if r['status'] == "대기중" and st.button("✅ 승인", key=f"ok_{r['id']}"):
                        r['status']="승인됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 인사총무팀 전용 관리 시스템")
    if not st.session_state.admin_logged_in:
        a_id, a_pw = st.text_input("Admin ID", key="ad_id"), st.text_input("Admin PW", type="password", key="ad_pw")
        if st.button("로그인", key="ad_login"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃", key="ad_logout"): st.session_state.admin_logged_in = False; st.rerun()
        st.divider()
        
        # [신규 등록] 요청하신 3단 레이아웃
        with st.expander("👨‍🏫 멘토 신규 등록"):
            r1_1, r1_2, r1_3, r1_4 = st.columns(4)
            nm, np, nt, n_pw = r1_1.text_input("성함", key="n_nm"), r1_2.text_input("직급", key="n_np"), r1_3.text_input("팀명", key="n_nt"), r1_4.text_input("비번", key="n_pw")
            r2_1, r2_2 = st.columns([1.5, 2.5])
            ne, nex = r2_1.text_input("이메일", key="n_ne"), r2_2.text_input("전문분야", key="n_nx")
            ng = st.text_area("인사말", key="n_ng")
            if st.button("멘토 등록", key="n_btn"):
                st.session_state.mentors_data.append({"name":nm, "position":np, "team":nt, "pw":n_pw, "expertise":nex, "greeting":ng, "email":ne})
                safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()

        # [수정/삭제] 동일한 3단 레이아웃
        with st.expander("📋 멘토 수정/삭제", expanded=True):
            for i, m in enumerate(st.session_state.mentors_data):
                st.markdown(f"**[{m['name']}] 정보 관리**")
                er1_1, er1_2, er1_3, er1_4 = st.columns(4)
                un, up, ut, upw = er1_1.text_input("성함", m['name'], key=f"un_{i}"), er1_2.text_input("직급", m.get('position',''), key=f"up_{i}"), er1_3.text_input("팀명", m.get('team',''), key=f"ut_{i}"), er1_4.text_input("비번", m.get('pw',''), key=f"upw_{i}")
                er2_1, er2_2 = st.columns([1.5, 2.5])
                uem, uex = er2_1.text_input("이메일", m.get('email',''), key=f"ue_{i}"), er2_2.text_input("전문분야", m.get('expertise',''), key=f"ux_{i}")
                ug = st.text_area("인사말", m.get('greeting',''), key=f"ug_{i}")
                
                eb1, eb2 = st.columns([1, 8])
                if eb1.button("💾 저장", key=f"sv_{i}"):
                    st.session_state.mentors_data[i].update({"name":un, "position":up, "team":ut, "pw":upw, "email":uem, "expertise":uex, "greeting":ug})
                    safe_save(ws_mentors, st.session_state.mentors_data); st.success("수정 완료"); st.rerun()
                if eb2.button("❌ 삭제", key=f"dl_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                st.divider()
