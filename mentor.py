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

# [3] 📱 모바일 겹침 방지 및 디자인 최적화 CSS
style_css = """
    <style>
    /* 입력창 간격 확보 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 12px !important;
    }

    /* 모바일 반응형 디자인 (768px 이하) */
    @media (max-width: 768px) {
        /* 익스팬더 제목이 사라지지 않게 하고 겹침 방지 */
        div[data-testid="stExpander"] details summary p {
            display: block !important;
            visibility: visible !important;
            font-size: 15px !important;
            line-height: 1.5 !important;
            color: #31333F !important;
        }
        
        /* 시스템 내부 잔상(_arr, _down) 글자만 투명하게 처리 */
        div[data-testid="stExpander"] details summary span {
            font-size: 0 !important;
            color: transparent !important;
        }

        /* 탭 메뉴 글자 크기 최적화 */
        button[data-baseweb="tab"] {
            font-size: 13px !important;
            padding: 8px !important;
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
# 💾 데이터 로드 및 저장 함수
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
# 📧 이메일 발송 함수
# ==========================================
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
    except: pass

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성 (모든 메뉴 포함)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    with st.expander("📢 실시간 예약 가능 현황 확인하기", expanded=True):
        if not st.session_state.available_slots:
            st.info("현재 등록된 멘토링 일정이 없습니다.")
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
                    st.success(f"✅ **{m}** 멘토님 : {', '.join(sorted(list(infos)))} 예약 가능")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        mentee_name = st.text_input("신청자 성함")
        mentee_pos = st.text_input("직급")
    with col2:
        mentee_team = st.text_input("팀명")
        mentee_email = st.text_input("사내 이메일 주소")

    selected_m = st.selectbox("상담받을 멘토 선택", mentor_names)
    sel_date = st.date_input("희망 날짜 선택", datetime.date.today() + datetime.timedelta(days=1))
    
    slots_found = [s for s in st.session_state.available_slots if s['mentor']==selected_m and s['date']==sel_date]
    if slots_found:
        st.info(f"📍 {slots_found[0].get('location','장소 미지정')} | ⏰ {slots_found[0]['start']}~{slots_found[0]['end']}")
        topic = st.text_area("상담 주제 (필수)")
        if st.button("🚀 예약 신청하기", type="primary", use_container_width=True):
            if not mentee_name or selected_m == "선택해주세요" or not topic:
                st.error("모든 항목을 입력해주세요.")
            else:
                new_res = {"id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": mentee_name, "mentee_position": mentee_pos, "mentee_team": mentee_team, "mentee_email": mentee_email, "date": sel_date, "start_time": slots_found[0]['start'], "end_time": slots_found[0]['end'], "topic": topic, "location": slots_found[0].get('location',''), "status": "대기중"}
                st.session_state.reservations.append(new_res); safe_save(ws_res, st.session_state.reservations)
                
                # 멘토 알림 발송
                m_info = next((m for m in st.session_state.mentors_data if m['name']==selected_m), None)
                if m_info and m_info.get('email'):
                    send_email(m_info['email'], "[DaeHanFeed] 새로운 멘토링 신청", f"{mentee_name}님의 신청이 접수되었습니다.")
                st.balloons(); st.success("신청 완료!"); st.rerun()
    elif selected_m != "선택해주세요":
        st.warning("선택하신 날짜에 일정이 없습니다.")

# --- [💼 탭 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 나의 멘토링 일정 관리")
    m_login = st.selectbox("본인 성함 선택", mentor_names, key="m_login_t2")
    if m_login != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_login), None)
        if m_info and st.text_input("멘토 비밀번호 입력", type="password", key="m_pw_t2") == str(m_info['pw']):
            st.markdown("#### ✨ 새로운 일정 등록")
            c1, c2, c3, c4 = st.columns(4)
            d_val = c1.date_input("날짜", key="d_t2")
            s_val = c2.time_input("시작", datetime.time(13,0), key="s_t2")
            e_val = c3.time_input("종료", datetime.time(17,0), key="e_t2")
            loc_val = c4.text_input("상담 장소", key="l_t2")
            if st.button("일정 등록하기"):
                st.session_state.available_slots.append({"mentor": m_login, "date": d_val, "start": s_val, "end": e_val, "location": loc_val})
                safe_save(ws_slots, st.session_state.available_slots); st.success("등록됨"); st.rerun()

            st.divider(); st.markdown("#### 🗑️ 등록된 일정 목록")
            for i, s in enumerate([x for x in st.session_state.available_slots if x['mentor']==m_login]):
                col_a, col_b = st.columns([4,1])
                col_a.write(f"📅 {s['date']} | ⏰ {s['start']}~{s['end']} | 📍 {s.get('location','')}")
                if col_b.button("삭제", key=f"del_s_{i}"):
                    st.session_state.available_slots.remove(s); safe_save(ws_slots, st.session_state.available_slots); st.rerun()

# --- [📋 탭 3: 멘토 예약 관리] ---
with tab3:
    st.subheader("📋 멘티 신청 현황 관리")
    m_sel_t3 = st.selectbox("본인 성함 선택", mentor_names, key="m_sel_t3")
    if m_sel_t3 != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_sel_t3), None)
        if m_info and st.text_input("비밀번호 확인", type="password", key="pw_t3") == str(m_info['pw']):
            my_res = [r for r in st.session_state.reservations if r['mentor']==m_sel_t3]
            if not my_res: st.info("신청 내역이 없습니다.")
            for r in my_res:
                with st.expander(f"[{r['status']}] {r['date']} | {r['mentee_name']}님"):
                    st.write(f"주제: {r['topic']}")
                    if r['status'] == "대기중":
                        ca, cb = st.columns(2)
                        if ca.button("✅ 승인", key=f"ok_{r['id']}"):
                            r['status'] = "승인됨"; safe_save(ws_res, st.session_state.reservations)
                            if r.get('mentee_email'):
                                send_email(r['mentee_email'], "[DaeHanFeed] 예약 승인 안내", f"멘토링 예약이 승인되었습니다. ({r['date']})")
                            st.rerun()
                        if cb.button("❌ 거절", key=f"no_{r['id']}"):
                            r['status'] = "거절됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 인사총무팀 전용 관리 시스템")
    if not st.session_state.admin_logged_in:
        a_id, a_pw = st.text_input("Admin ID"), st.text_input("Admin PW", type="password")
        if st.button("관리자 로그인"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
            else: st.error("정보 불일치")
    else:
        if st.button("로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        with st.expander("👨‍🏫 멘토 신규 등록"):
            nc1, nc2, nc3, nc4 = st.columns(4)
            n_m, n_p, n_t, n_pw = nc1.text_input("성함"), nc2.text_input("직급"), nc3.text_input("팀명"), nc4.text_input("비번")
            n_e, n_em, n_g = st.text_input("전문분야"), st.text_input("이메일"), st.text_area("인사말")
            if st.button("멘토 등록"):
                st.session_state.mentors_data.append({"name":n_m, "position":n_p, "team":n_t, "pw":n_pw, "expertise":n_e, "greeting":n_g, "email":n_em})
                safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
        
        with st.expander("📋 멘토 정보 수정/삭제"):
            for i, m in enumerate(st.session_state.mentors_data):
                st.write(f"**{m['name']} 멘토 관리**")
                u_name = st.text_input("이름", m['name'], key=f"un_{i}")
                u_email = st.text_input("이메일", m.get('email',''), key=f"ue_{i}")
                u_exp = st.text_input("전문분야", m.get('expertise',''), key=f"ux_{i}")
                u_greet = st.text_area("인사말", m.get('greeting',''), key=f"ug_{i}")
                
                b1, b2 = st.columns([1, 8])
                if b1.button("💾 저장", key=f"save_{i}"):
                    st.session_state.mentors_data[i].update({"name":u_name, "email":u_email, "expertise":u_exp, "greeting":u_greet})
                    safe_save(ws_mentors, st.session_state.mentors_data); st.success("수정됨"); st.rerun()
                if b2.button("❌ 삭제", key=f"del_{i}"):
                    st.session_state.mentors_data.pop(i); safe_save(ws_mentors, st.session_state.mentors_data); st.rerun()
                st.divider()
