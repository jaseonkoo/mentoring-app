import streamlit as st
import datetime
import uuid
import pandas as pd
import gspread
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from oauth2client.service_account import ServiceAccountCredentials
import time

# [1] 브라우저 및 페이지 기본 설정
st.set_page_config(page_title="DaeHanFeed Mentoring", page_icon="🤝", layout="wide")

SYSTEM_URL = "https://share.streamlit.io/jaseonkoo/mentoring-app/main/mentor.py"
WEEKS = ['월', '화', '수', '목', '금', '토', '일']

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# 멘토 이름 변경 시 비번 입력창 초기화 콜백
def reset_pw_t2():
    if "m_pw_t2" in st.session_state: st.session_state["m_pw_t2"] = ""
def reset_pw_t3():
    if "m_pw_t3" in st.session_state: st.session_state["m_pw_t3"] = ""

# [2] 📱 모바일 최적화 및 제목 노출 보장 CSS
st.markdown("""
    <style>
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput { margin-bottom: 12px !important; }
    @media (max-width: 768px) {
        div[data-testid="stExpander"] details summary p { display: block !important; visibility: visible !important; line-height: 1.6 !important; font-size: 15px !important; }
        div[data-testid="stExpander"] details summary span:not(:has(p)) { font-size: 0 !important; color: transparent !important; }
    }
    </style>
""", unsafe_allow_html=True)

if not st.session_state.admin_logged_in:
    st.markdown("<style>#MainMenu, header, footer, .stDeployButton {visibility: hidden; display:none;}</style>", unsafe_allow_html=True)

st.title("🤝 DaeHanFeed Mentoring")
st.caption("대한사료 임직원 간의 성장을 돕는 실시간 소통 플랫폼")
st.markdown("---")

# ==========================================
# ☁️ 구글 스프레드시트 연결 및 데이터 로드 (안정화)
# ==========================================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_gspread():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open("멘토링예약DB")

# API 과부하 방지를 위해 15초간 캐시 유지
@st.cache_data(ttl=15)
def get_sheet_data(sheet_name):
    doc = init_gspread()
    return doc.worksheet(sheet_name).get_all_records()

def fetch_latest_data():
    try:
        # 데이터 불러오기
        st.session_state.mentors_data = get_sheet_data("mentors")
        ad_list = get_sheet_data("admin")
        st.session_state.admin_info = ad_list[0] if ad_list else {"id": "admin", "pw": "dhfeed1947"}
        
        # 슬롯 데이터 날짜/시간 포맷팅
        slots = get_sheet_data("slots")
        for s in slots:
            s['date'] = datetime.datetime.strptime(str(s['date']), "%Y-%m-%d").date()
            s['start'] = datetime.datetime.strptime(str(s['start']), "%H:%M:%S").time()
            s['end'] = datetime.datetime.strptime(str(s['end']), "%H:%M:%S").time()
        st.session_state.available_slots = slots
        
        # 예약 내역 날짜/시간 포맷팅
        res = get_sheet_data("reservations")
        for r in res:
            r['date'] = datetime.datetime.strptime(str(r['date']), "%Y-%m-%d").date()
            r['start_time'] = datetime.datetime.strptime(str(r['start_time']), "%H:%M:%S").time()
            r['end_time'] = datetime.datetime.strptime(str(r['end_time']), "%H:%M:%S").time()
        st.session_state.reservations = res
    except:
        if "available_slots" not in st.session_state:
            st.error("⚠️ 구글 시트 데이터를 가져오는 중입니다. 잠시만 기다려주세요.")

# 페이지 로딩 시 데이터 페칭
fetch_latest_data()

def safe_save(ws_name, data_list):
    try:
        doc = init_gspread()
        ws = doc.worksheet(ws_name)
        ws.clear()
        if data_list:
            df = pd.DataFrame(data_list)
            for c in ['date', 'start', 'end', 'start_time', 'end_time']:
                if c in df.columns: df[c] = df[c].astype(str)
            df = df.fillna("")
            ws.update([df.columns.values.tolist()] + df.values.tolist())
        # ✨ 저장 성공 시 캐시를 즉시 비우고 다시 불러와 동기화
        st.cache_data.clear()
        fetch_latest_data()
    except:
        st.error("⚠️ 저장 실패! 구글 시트 연결 상태를 확인해 주세요.")

def send_email(to_email, subject, body):
    SMTP_S, SMTP_P = "smtp.dooray.com", 465
    U, P = st.secrets["email"]["smtp_user"], st.secrets["email"]["smtp_password"]
    try:
        msg = MIMEText(body, 'plain', 'utf-8'); msg['Subject'], msg['From'], msg['To'] = Header(subject, 'utf-8'), U, to_email
        with smtplib.SMTP_SSL(SMTP_S, SMTP_P) as server: server.login(U, P); server.sendmail(U, to_email, msg.as_string())
    except: pass

def is_company_email(email): return email.strip().lower().endswith("@daehanfeed.co.kr")

def generate_time_slots(start_time, end_time):
    slots = []
    curr = datetime.datetime.combine(datetime.date.today(), start_time)
    end = datetime.datetime.combine(datetime.date.today(), end_time)
    while curr <= end: slots.append(curr.time()); curr += datetime.timedelta(minutes=30)
    return slots

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.get('mentors_data', [])]

# ==========================================
# 📊 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 실시간 예약 가능 현황", expanded=True):
        if not st.session_state.get('available_slots'): st.info("등록된 일정이 없습니다.")
        else:
            summ = {}
            for s in st.session_state.available_slots:
                booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not booked:
                    w_day = WEEKS[s['date'].weekday()]
                    info = f"{s['date'].strftime('%m/%d')}({w_day}) {s['start'].strftime('%H:%M')}~{s['end'].strftime('%H:%M')}"
                    summ[s['mentor']] = summ.get(s['mentor'], set()) | {info}
            for m, infos in summ.items(): st.success(f"✅ **{m}** : {', '.join(sorted(list(infos)))}")
    
    if st.button("🔄 현황 새로고침"): st.cache_data.clear(); fetch_latest_data(); st.rerun()

    st.markdown("---")
    c1, c2 = st.columns(2)
    m_name, m_pos = c1.text_input("신청자 성함", key="m_n_t1"), c1.text_input("직급", key="m_p_t1")
    m_team, m_email = c2.text_input("신청자 팀명", key="m_t_t1"), c2.text_input("사내 이메일", key="m_e_t1", placeholder="example@daehanfeed.co.kr")
    if m_email and not is_company_email(m_email): st.error("🚫 @daehanfeed.co.kr 전용")

    col_sel, col_prof = st.columns([1.2, 1])
    with col_sel:
        selected_m = st.selectbox("멘토 선택", mentor_names, key="m_s_t1")
        sel_date = st.date_input("날짜 선택", datetime.date.today() + datetime.timedelta(days=1), key="d_s_t1")
        slots = [s for s in st.session_state.get('available_slots', []) if s['mentor']==selected_m and s['date']==sel_date]
        if slots:
            w_day_sel = WEEKS[sel_date.weekday()]
            st.info(f"⏰ {sel_date.strftime('%m/%d')}({w_day_sel}) {slots[0]['start']} ~ {slots[0]['end']}")
            p_t = generate_time_slots(slots[0]['start'], slots[0]['end'])
            ct1, ct2 = st.columns(2); ts = ct1.selectbox("시작", p_t, format_func=lambda x: x.strftime("%H:%M"), key="ts_t1"); te = ct2.selectbox("종료", [t for t in p_t if t > ts] if [t for t in p_t if t > ts] else [ts], format_func=lambda x: x.strftime("%H:%M"), key="te_t1")
            topic = st.text_area("상담 주제 (필수)", key="tp_t1")
            if st.button("🚀 예약 신청하기", type="primary", use_container_width=True, key="bt1"):
                if not m_name or not topic or not is_company_email(m_email): st.warning("⚠️ 정보 부족")
                else:
                    with st.status("📡 전송 중..."):
                        new_res = {"id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": m_name, "mentee_position": m_pos, "mentee_team": m_team, "mentee_email": m_email, "date": sel_date, "start_time": ts, "end_time": te, "topic": topic, "location": slots[0].get('location',''), "status": "대기중"}
                        st.session_state.reservations.append(new_res); safe_save("reservations", st.session_state.reservations)
                        m_info = next((m for m in st.session_state.mentors_data if m['name']==selected_m), None)
                        if m_info and m_info.get('email'):
                            body = f"안녕하세요 {selected_m} 멘토님!\n\n{m_name}님께서 멘토링을 신청하셨습니다.\n- 일시: {sel_date}({w_day_sel}) {ts} ~ {te}\n- 주제: {topic}\n\n▶ {SYSTEM_URL}"
                            send_email(m_info['email'], f"[DaeHanFeed] 새로운 신청", body)
                    st.balloons(); time.sleep(1.5); st.rerun()

    with col_prof:
        if selected_m != "선택해주세요":
            p = next((m for m in st.session_state.get('mentors_data', []) if m['name'] == selected_m), None)
            if p: st.markdown(f"""<div style="border: 2px solid #4A90E2; padding: 25px; border-radius: 12px; background-color: #f0f7ff;"><h3 style="margin-top:0; color: #1E3A8A;">🎖️ {p['name']} {p.get('position','')} 멘토</h3><p>🏢 소속: {p.get('team','')}<br>🎯 전문분야: {p.get('expertise','')}</p><div style="margin-top: 15px; background-color: white; padding: 15px; border-radius: 8px; border-left: 5px solid #4A90E2;"><p style="font-size: 0.9em;"><i>"{p.get('greeting','')}"</i></p></div></div>""", unsafe_allow_html=True)

# --- [💼 탭 2: 멘토 일정 관리 (리스트 노출 보강)] ---
with tab2:
    st.subheader("💼 나의 멘토링 일정 및 계정 관리")
    m_log2 = st.selectbox("본인 성함 선택", mentor_names, key="m_log_t2", on_change=reset_pw_t2)
    if m_log2 != "선택해주세요":
        minfo = next((m for m in st.session_state.get('mentors_data', []) if m['name']==m_log2), None)
        if minfo and st.text_input("비밀번호 입력", type="password", key="m_pw_t2") == str(minfo['pw']):
            with st.expander("🔑 비밀번호 변경하기"):
                new_m_pw = st.text_input("새 비밀번호", type="password", key="m_new_pw_f")
                if st.button("업데이트"):
                    for m in st.session_state.mentors_data:
                        if m['name'] == m_log2: m['pw'] = new_m_pw
                    safe_save("mentors", st.session_state.mentors_data); st.success("변경 완료!"); st.rerun()
            st.divider()
            c2_1, c2_2, c2_3, c2_4 = st.columns(4)
            dv = c2_1.date_input("날짜", key="sd_t2")
            sv = c2_2.time_input("시작", datetime.time(0,0), key="ss_t2") # 00:00 셋팅 유지
            ev = c2_3.time_input("종료", datetime.time(0,0), key="se_t2") # 00:00 셋팅 유지
            lv = c2_4.text_input("장소", key="sl_t2")
            
            if st.button("🗓️ 일정 등록하기", type="primary", use_container_width=True, key="sb_t2"):
                with st.status("📡 저장 중..."):
                    st.session_state.available_slots.append({"mentor": m_log2, "date": dv, "start": sv, "end": ev, "location": lv})
                    safe_save("slots", st.session_state.available_slots)
                st.snow(); st.success("등록 완료!"); time.sleep(1); st.rerun()
            
            # ✨ [리스트 즉시 노출 핵심 영역]
            st.divider()
            st.markdown(f"#### 🗑️ {m_log2} 멘토님의 등록 일정 목록")
            my_slots = [x for x in st.session_state.get('available_slots', []) if x['mentor'] == m_log2]
            
            if not my_slots:
                st.info("현재 등록된 일정이 없습니다.")
            else:
                for i, s in enumerate(my_slots):
                    w_s = WEEKS[s['date'].weekday()]
                    col_a, col_b = st.columns([4, 1])
                    col_a.write(f"📅 {s['date']}({w_s}) | ⏰ {s['start']} ~ {s['end']} | 📍 {s.get('location','')}")
                    if col_b.button("삭제", key=f"del_s_{i}"):
                        st.session_state.available_slots.remove(s)
                        safe_save("slots", st.session_state.available_slots)
                        st.rerun()

# --- [Tab 3, 4 로직 유지] ---
with tab3:
    st.subheader("📋 멘티 신청 현황 관리")
    m_sel3 = st.selectbox("본인 성함 선택", mentor_names, key="m_sel_t3", on_change=reset_pw_t3)
    if m_sel3 != "선택해주세요":
        minfo3 = next((m for m in st.session_state.get('mentors_data', []) if m['name']==m_sel3), None)
        if minfo3 and st.text_input("비번 확인", type="password", key="m_pw_t3") == str(minfo3['pw']):
            my_res = [x for x in st.session_state.get('reservations', []) if x['mentor']==m_sel3]
            for r in my_res:
                with st.expander(f"[{r['status']}] {r['date']}({WEEKS[r['date'].weekday()]}) | {r['mentee_name']}님"):
                    st.write(f"👤 {r['mentee_name']} | 📝 주제: {r['topic']}")
                    if r['status'] == "대기중":
                        b1, b2 = st.columns(2)
                        if b1.button("✅ 승인", key=f"ok_{r['id']}", use_container_width=True):
                            r['status']="승인됨"; safe_save("reservations", st.session_state.reservations); st.rerun()
                        if b2.button("❌ 거절", key=f"no_{r['id']}", use_container_width=True):
                            r['status']="거절됨"; safe_save("reservations", st.session_state.reservations); st.rerun()

with tab4:
    st.subheader("👑 관리자 전용")
    if not st.session_state.admin_logged_in:
        aid, apw = st.text_input("ID", key="ad_id"), st.text_input("PW", type="password", key="ad_pw")
        if st.button("로그인") and aid == st.session_state.admin_info['id'] and apw == str(st.session_state.admin_info['pw']):
            st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        with st.expander("🔐 관리자 비밀번호 변경"):
            new_ad_pw = st.text_input("새 비번", type="password", key="nad_pw")
            if st.button("비번 업데이트") and new_ad_pw:
                st.session_state.admin_info['pw'] = new_ad_pw
                safe_save("admin", [st.session_state.admin_info]); st.success("완료")
        with st.expander("👨‍🏫 멘토 신규 등록"):
            r1, r2, r3, r4 = st.columns(4); nm, np, nt, n_pw = r1.text_input("성함",key="n1"), r2.text_input("직급",key="n2"), r3.text_input("팀명",key="n3"), r4.text_input("비번",key="n4")
            e1, e2 = st.columns([1.5, 2.5]); ne, nx = e1.text_input("이메일",key="n5"), e2.text_input("전문",key="n6"); ng = st.text_area("인사말", key="n7")
            if st.button("등록하기") and is_company_email(ne):
                st.session_state.mentors_data.append({"name":nm, "position":np, "team":nt, "pw":n_pw, "expertise":nx, "greeting":ng, "email":ne})
                safe_save("mentors", st.session_state.mentors_data); st.rerun()
