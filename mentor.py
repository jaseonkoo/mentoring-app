import streamlit as st
import datetime
import uuid
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# [1] 브라우저 탭 설정 및 제목
st.set_page_config(page_title="Daehan Feed Mentoring", page_icon="🤝", layout="wide")

# [2] 관리자 외 상단 메뉴 숨기기 마법
if not st.session_state.get("admin_logged_in", False):
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        </style>
    """, unsafe_allow_html=True)

# 메인 타이틀
st.title("🤝 Daehan Feed Mentoring")
st.caption("대한사료 임직원을 위한 실시간 멘토링 예약 시스템")
st.markdown("---")

# ==========================================
# ☁️ [핵심] 구글 스프레드시트 연결
# ==========================================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_gspread():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    doc = client.open("멘토링예약DB")
    
    ws_slots = doc.worksheet("slots") if "slots" in [w.title for w in doc.worksheets()] else doc.add_worksheet("slots", 1000, 20)
    ws_res = doc.worksheet("reservations") if "reservations" in [w.title for w in doc.worksheets()] else doc.add_worksheet("reservations", 1000, 20)
    ws_mentors = doc.worksheet("mentors") if "mentors" in [w.title for w in doc.worksheets()] else doc.add_worksheet("mentors", 100, 10)
    ws_admin = doc.worksheet("admin") if "admin" in [w.title for w in doc.worksheets()] else doc.add_worksheet("admin", 10, 2)
    
    return ws_slots, ws_res, ws_mentors, ws_admin

ws_slots, ws_res, ws_mentors, ws_admin = init_gspread()

# ==========================================
# 💾 데이터 로드 및 저장 함수 (빈칸 방지 포함)
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
        if 'date' in df.columns: df['date'] = df['date'].astype(str)
        if 'start' in df.columns: df['start'] = df['start'].astype(str)
        if 'end' in df.columns: df['end'] = df['end'].astype(str)
        if 'start_time' in df.columns: df['start_time'] = df['start_time'].astype(str)
        if 'end_time' in df.columns: df['end_time'] = df['end_time'].astype(str)
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())

if "data_loaded" not in st.session_state:
    load_data()
    st.session_state.data_loaded = True

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    
    # [A] 현재 예약 가능한 멘토 현황판
    with st.expander("📢 실시간 예약 가능 멘토 확인하기", expanded=True):
        if not st.session_state.available_slots:
            st.info("현재 등록된 일정이 없습니다.")
        else:
            avail_dict = {}
            for s in st.session_state.available_slots:
                booked = sum(1 for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if booked < 1: # 단순화: 슬롯당 1명 기준
                    d_str = s['date'].strftime("%m/%d")
                    avail_dict[s['mentor']] = avail_dict.get(s['mentor'], set()) | {d_str}
            
            if not avail_dict: st.write("모든 일정이 마감되었습니다.")
            else:
                for m, dates in avail_dict.items():
                    st.write(f"✅ **{m}** : {', '.join(sorted(list(dates)))} 가능")

    st.markdown("---")

    # [B] 정보 입력 섹션
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1: m_name = st.text_input("신청자 성함")
    with col_i2: m_email = st.text_input("사내 이메일")
    with col_i3: sel_mentor = st.selectbox("1. 상담받을 멘토 선택", mentor_names)

    # [C] 멘토 프로필 명함 (선택 시에만 중앙에 크게 표시)
    if sel_mentor != "선택해주세요":
        prof = next((m for m in st.session_state.mentors_data if m['name'] == sel_mentor), None)
        if prof:
            st.markdown(f"""
                <div style="border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f9f9f9; margin: 10px 0;">
                    <h3 style="margin-top:0;">🎖️ {prof['name']} 멘토 프로필</h3>
                    <p><b>🏢 소속:</b> {prof.get('team','미지정')} | <b>🎯 전문영역:</b> {prof.get('expertise','미지정')}</p>
                    <p style="font-style: italic; color: #555;">" {prof.get('greeting','반갑습니다!')} "</p>
                </div>
            """, unsafe_allow_html=True)

    # [D] 일정 및 장소 선택 (좌우 밸런스 조정)
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        sel_date = st.date_input("2. 희망 날짜", datetime.date.today() + datetime.timedelta(days=1))
    
    with col_right := col_d2:
        slots = [s for s in st.session_state.available_slots if s['mentor']==sel_mentor and s['date']==sel_date]
        if not slots:
            if sel_mentor != "선택해주세요": st.warning("해당 날짜에 가능한 시간이 없습니다.")
        else:
            st.info("✅ 멘토가 지정한 장소와 시간을 확인하세요.")
            for s in slots:
                loc = s.get('location', '장소 미지정')
                st.write(f"⏰ {s['start'].strftime('%H:%M')} ~ {s['end'].strftime('%H:%M')} | 📍 **{loc}**")
            
            c_s, c_e = st.columns(2)
            with c_s: t_start = st.time_input("3. 시작 시간", slots[0]['start'])
            with c_e: t_end = st.time_input("4. 종료 시간", slots[0]['end'])

    m_topic = st.text_area("5. 사전 질문 및 상담 주제", placeholder="구체적으로 적어주실수록 멘토링의 질이 높아집니다.")

    if st.button("🚀 예약 신청하기", type="primary", use_container_width=True):
        if not m_name or sel_mentor == "선택해주세요" or not m_topic:
            st.error("필수 정보를 모두 입력해주세요.")
        else:
            new_res = {"id": str(uuid.uuid4()), "mentor": sel_mentor, "mentee_name": m_name, "mentee_email": m_email,
                       "date": sel_date, "start_time": t_start, "end_time": t_end, "topic": m_topic, "status": "대기중"}
            st.session_state.reservations.append(new_res)
            safe_save(ws_res, st.session_state.reservations)
            st.success("신청 완료! 멘토의 승인을 기다려주세요.")

# --- [💼 탭 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 나의 멘토링 일정 관리")
    m_sel = st.selectbox("성함 선택", mentor_names, key="m_sel_t2")
    if m_sel != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_sel), None)
        if m_info and st.text_input("비밀번호", type="password") == str(m_info['pw']):
            
            with st.expander("🔑 비밀번호 변경"):
                new_pw = st.text_input("새 비밀번호", type="password")
                if st.button("변경"):
                    m_info['pw'] = new_pw
                    safe_save(ws_mentors, st.session_state.mentors_data)
                    st.success("변경되었습니다.")

            st.markdown("#### ✨ 새로운 일정 열기")
            c1, c2, c3 = st.columns(3)
            with c1: d_val = st.date_input("날짜", datetime.date.today(), key="d_t2")
            with c2: s_val = st.time_input("시작", datetime.time(13,0), key="s_t2")
            with c3: e_val = st.time_input("종료", datetime.time(17,0), key="e_t2")
            loc_val = st.text_input("📍 상담 장소 (예: 본사 2층 회의실, 화상회의 등)", placeholder="정확한 장소를 적어주세요.")
            
            if st.button("일정 등록"):
                st.session_state.available_slots.append({"mentor": m_sel, "date": d_val, "start": s_val, "end": e_val, "location": loc_val})
                safe_save(ws_slots, st.session_state.available_slots)
                st.rerun()

            st.divider()
            st.markdown("#### 🗑️ 등록된 일정")
            for i, s in enumerate([x for x in st.session_state.available_slots if x['mentor']==m_sel]):
                col_a, col_b = st.columns([4,1])
                col_a.write(f"📅 {s['date']} | ⏰ {s['start']}~{s['end']} | 📍 {s.get('location','')}")
                if col_b.button("삭제", key=f"del_{i}"):
                    st.session_state.available_slots.remove(s)
                    safe_save(ws_slots, st.session_state.available_slots)
                    st.rerun()

# --- [📋 탭 3: 멘토 예약 관리] ---
with tab3:
    st.subheader("📋 신청 내역 승인/관리")
    # (기존 승인/거절/취소 로직과 동일하되 디자인만 정돈)
    m_sel_t3 = st.selectbox("성함 선택", mentor_names, key="m_sel_t3")
    if m_sel_t3 != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_sel_t3), None)
        if m_info and st.text_input("비밀번호 확인", type="password", key="pw_t3") == str(m_info['pw']):
            my_res = [r for r in st.session_state.reservations if r['mentor']==m_sel_t3]
            for r in my_res:
                with st.expander(f"[{r['status']}] {r['mentee_name']}님 - {r['date']}"):
                    st.write(f"⏰ {r['start_time']}~{r['end_time']}")
                    st.write(f"💬 주제: {r['topic']}")
                    if r['status'] == "대기중":
                        ca, cb = st.columns(2)
                        if ca.button("✅ 승인", key=f"ok_{r['id']}"):
                            r['status']="승인됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()
                        if cb.button("❌ 거절", key=f"no_{r['id']}"):
                            r['status']="거절됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()
                    elif r['status'] == "승인됨":
                        if st.button("🚫 예약 취소", key=f"can_{r['id']}"):
                            r['status']="취소됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 시스템 관리")
    if not st.session_state.admin_logged_in:
        if st.text_input("Admin ID") == st.session_state.admin_info['id'] and st.text_input("Admin PW", type="password") == str(st.session_state.admin_info['pw']):
            if st.button("관리자 로그인"): st.session_state.admin_logged_in = True; st.rerun()
    else:
        if st.button("로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        st.divider()
        # 멘토 등록/수정 로직 (생략 없이 유지)
        with st.expander("👨‍🏫 신규 멘토 등록"):
            c1, c2, c3 = st.columns(3)
            n_m = c1.text_input("이름")
            n_t = c2.text_input("팀명")
            n_p = c3.text_input("비번")
            n_e = st.text_input("전문영역")
            n_g = st.text_area("인사말")
            if st.button("등록하기"):
                st.session_state.mentors_data.append({"name":n_m, "team":n_t, "pw":n_p, "expertise":n_e, "greeting":n_g, "email":""})
                safe_save(ws_mentors, st.session_state.mentors_data)
                st.rerun()
