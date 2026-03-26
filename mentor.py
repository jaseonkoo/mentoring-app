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

# [3] 📱 모바일 최적화 및 디자인 CSS (제목 노출 보장)
style_css = """
    <style>
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 12px !important;
    }
    @media (max-width: 768px) {
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            visibility: visible !important;
            line-height: 1.5 !important;
            font-size: 15px !important;
        }
        div[data-testid="stExpander"] details summary span:not(:has(p)) {
            font-size: 0 !important;
            color: transparent !important;
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

def send_email(to_email, subject, body):
    SMTP_S, SMTP_P = "smtp.dooray.com", 465
    U, P = st.secrets["email"]["smtp_user"], st.secrets["email"]["smtp_password"]
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'], msg['From'], msg['To'] = Header(subject, 'utf-8'), U, to_email
        with smtplib.SMTP_SSL(SMTP_S, SMTP_P) as server:
            server.login(U, P)
            server.sendmail(U, to_email, msg.as_string())
        st.toast(f"✅ 알림 메일 발송 완료")
    except: pass

def is_company_email(email):
    return email.strip().lower().endswith("@daehanfeed.co.kr")

def generate_time_slots(start_time, end_time):
    slots = []
    curr = datetime.datetime.combine(datetime.date.today(), start_time)
    end = datetime.datetime.combine(datetime.date.today(), end_time)
    while curr <= end:
        slots.append(curr.time())
        curr += datetime.timedelta(minutes=30)
    return slots

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성
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

    st.markdown("---")
    c1, c2 = st.columns(2)
    m_name = c1.text_input("신청자 성함", key="m_name_t1")
    m_pos = c1.text_input("신청자 직급", key="m_pos_t1")
    m_team = c2.text_input("신청자 팀명", key="m_team_t1")
    m_email = c2.text_input("사내 이메일 주소", key="m_email_t1")
    if m_email and not is_company_email(m_email):
        st.error("🚫 @daehanfeed.co.kr 이메일만 사용 가능합니다.")

    col_sel, col_prof = st.columns([1.2, 1])
    with col_sel:
        selected_m = st.selectbox("멘토 선택", mentor_names, key="m_sel_t1")
        sel_date = st.date_input("날짜 선택", datetime.date.today() + datetime.timedelta(days=1), key="d_sel_t1")
        
        slots = [s for s in st.session_state.available_slots if s['mentor']==selected_m and s['date']==sel_date]
        if slots:
            st.info(f"📍 {slots[0].get('location','-')} | ⏰ {slots[0]['start']} ~ {slots[0]['end']}")
            p_times = generate_time_slots(slots[0]['start'], slots[0]['end'])
            ct1, ct2 = st.columns(2)
            t_s = ct1.selectbox("시작 시간", p_times, format_func=lambda x: x.strftime("%H:%M"), key="t_s_t1")
            p_es = [t for t in p_times if t > t_s]
            t_e = ct2.selectbox("종료 시간", p_es if p_es else [t_s], format_func=lambda x: x.strftime("%H:%M"), key="t_e_t1")
            topic = st.text_area("상담 주제 (필수)", key="topic_t1")
            
            if st.button("🚀 예약 신청하기", type="primary", use_container_width=True, key="btn_t1"):
                if not m_name or not topic or not is_company_email(m_email):
                    st.error("입력 정보를 확인해주세요.")
                else:
                    new_res = {"id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": m_name, "mentee_position": m_pos, "mentee_team": m_team, "mentee_email": m_email, "date": sel_date, "start_time": t_s, "end_time": t_e, "topic": topic, "location": slots[0].get('location',''), "status": "대기중"}
                    st.session_state.reservations.append(new_res); safe_save(ws_res, st.session_state.reservations); st.balloons(); st.rerun()

    with col_prof:
        if selected_m != "선택해주세요":
            p = next((m for m in st.session_state.mentors_data if m['name'] == selected_m), None)
            if p:
                st.markdown(f"""
                    <div style="border: 2px solid #4A90E2; padding: 25px; border-radius: 12px; background-color: #f0f7ff;">
                        <h3 style="margin-top:0; color: #1E3A8A;">🎖️ {p['name']} {p.get('position','')} 멘토</h3>
                        <p>🏢 <b>소속:</b> {p.get('team','')}<br>🎯 <b>전문영역:</b> {p.get('expertise','')}</p>
                        <div style="margin-top: 15px; background-color: white; padding: 15px; border-radius: 8px; border-left: 5px solid #4A90E2;">
                            <p style="font-size: 0.9em;"><i>"{p.get('greeting','')}"</i></p>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

# --- [💼 탭 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 나의 일정 등록")
    m_log2 = st.selectbox("본인 성함 선택", mentor_names, key="m_log_t2")
    if m_log2 != "선택해주세요":
        minfo = next((m for m in st.session_state.mentors_data if m['name']==m_log2), None)
        if minfo and st.text_input("비밀번호", type="password", key="m_pw_t2") == str(minfo['pw']):
            c2_1, c2_2, c2_3, c2_4 = st.columns(4)
            dv, sv, ev, lv = c2_1.date_input("날짜", key="sd_t2"), c2_2.time_input("시작", key="ss_t2"), c2_3.time_input("종료", key="se_t2"), c2_4.text_input("장소", key="sl_t2")
            if st.button("일정 등록", key="sb_t2"):
                st.session_state.available_slots.append({"mentor": m_log2, "date": dv, "start": sv, "end": ev, "location": lv})
                safe_save(ws_slots, st.session_state.available_slots); st.rerun()

# --- [📋 탭 3: 멘토 예약 관리 (상세정보 보강)] ---
with tab3:
    st.subheader("📋 멘티 신청 현황 관리")
    m_sel3 = st.selectbox("본인 성함 선택", mentor_names, key="m_sel_t3")
    if m_sel3 != "선택해주세요":
        minfo3 = next((m for m in st.session_state.mentors_data if m['name']==m_sel3), None)
        if minfo3 and st.text_input("비번 확인", type="password", key="m_pw_t3") == str(minfo3['pw']):
            my_res = [x for x in st.session_state.reservations if x['mentor']==m_sel3]
            if not my_res: st.info("아직 신청 내역이 없습니다.")
            for r in my_res:
                # Expander 제목 구성
                exp_label = f"[{r['status']}] {r['date']} | {r['mentee_name']}님"
                with st.expander(exp_label):
                    # ✨ [복구 및 보강] 멘토가 봐야 할 멘티의 상세 정보
                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        st.markdown(f"**👤 신청자 정보**")
                        st.write(f"- 성함: {r['mentee_name']}")
                        st.write(f"- 소속/직급: {r.get('mentee_team','-')} / {r.get('mentee_position','-')}")
                        st.write(f"- 이메일: {r.get('mentee_email','-')}")
                    with col_res2:
                        st.markdown(f"**⏰ 멘토링 일정**")
                        st.write(f"- 일자: {r['date']}")
                        st.write(f"- 시간: {r['start_time']} ~ {r['end_time']}")
                        st.write(f"- 장소: {r.get('location','-')}")
                    
                    st.markdown("---")
                    st.markdown(f"**💬 상담 주제 및 질문 내용**")
                    st.info(r['topic'])
                    
                    if r['status'] == "대기중":
                        ca, cb = st.columns([1, 4])
                        if ca.button("✅ 승인", key=f"ok_{r['id']}"):
                            r['status']="승인됨"
                            safe_save(ws_res, st.session_state.reservations)
                            if r.get('mentee_email'):
                                send_email(r['mentee_email'], "[DaeHanFeed] 예약 승인", f"{m_sel3} 멘토님이 예약을 승인했습니다.")
                            st.rerun()
                        if cb.button("❌ 거절", key=f"no_{r['id']}"):
                            r['status']="거절됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 관리 시스템")
    if not st.session_state.admin_logged_in:
        aid, apw = st.text_input("ID", key="ad_id"), st.text_input("PW", type="password", key="ad_pw")
        if st.button("로그인"):
            if aid == st.session_state.admin_info['id'] and apw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        with st.expander("👨‍🏫 멘토 신규 등록"):
            r1, r2, r3, r4 = st.columns(4)
            nm, np, nt, n_pw = r1.text_input("성함",key="n1"), r2.text_input("직급",key="n2"), r3.text_input("팀명",key="n3"), r4.text_input("비번",key="n4")
            e1, e2 = st.columns([1.5, 2.5])
            ne, nx = e1.text_input("이메일",key="n5"), e2.text_input("전문분야",key="n6")
            ng = st.text_area("인사말", key="n7")
            if st.button("등록하기"):
                st.session_state.mentors_data.append({"name":nm, "position":np, "team":nt, "pw":n_pw, "expertise":nx, "greeting":ng, "email":ne})
                safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
        with st.expander("📋 멘토 수정/삭제", expanded=True):
            for i, m in enumerate(st.session_state.mentors_data):
                st.write(f"**{m['name']} 멘토**")
                c1, c2, c3, c4 = st.columns(4)
                un, up, ut, upw = c1.text_input("이름", m['name'], key=f"un_{i}"), c2.text_input("직급", m.get('position',''), key=f"up_{i}"), c3.text_input("팀", m.get('team',''), key=f"ut_{i}"), c4.text_input("비번", m.get('pw',''), key=f"upw_{i}")
                e1, e2 = st.columns([1.5, 2.5])
                ue, ux = e1.text_input("메일", m.get('email',''), key=f"ue_{i}"), e2.text_input("전문", m.get('expertise',''), key=f"ux_{i}")
                ug = st.text_area("인사말", m.get('greeting',''), key=f"ug_{i}")
                if st.button("💾 저장", key=f"sv_{i}"):
                    st.session_state.mentors_data[i].update({"name":un,"position":up,"team":ut,"pw":upw,"email":ue,"expertise":ux,"greeting":ug})
                    safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                if st.button("❌ 삭제", key=f"dl_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                st.divider()
