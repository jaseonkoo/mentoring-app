import streamlit as st
import datetime
import uuid
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# [1] 브라우저 및 페이지 기본 설정
st.set_page_config(page_title="Daehan Feed Mentoring", page_icon="🤝", layout="wide")

# [2] 디자인 발란스 및 여백 조정을 위한 마스터 CSS
st.markdown("""
    <style>
    /* 전체 요소 간 여백 최적화 */
    .stTextInput, .stSelectbox, .stDateInput, .stTextArea, .stTimeInput {
        margin-bottom: 20px;
    }
    /* 상단 메뉴 숨기기 */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
""", unsafe_allow_html=True)

# 프로그램 메인 타이틀
st.title("🤝 Daehan Feed Mentoring")
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

mentor_names = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 📊 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# --- [🙋‍♂️ 탭 1: 멘티 예약 신청] ---
with tab1:
    st.subheader("🗓️ 멘토링 예약 신청")
    
    with st.expander("📢 실시간 예약 가능 멘토 및 날짜 확인하기", expanded=True):
        if not st.session_state.available_slots:
            st.info("현재 등록된 멘토링 일정이 없습니다.")
        else:
            avail_summary = {}
            for s in st.session_state.available_slots:
                is_booked = any(r for r in st.session_state.reservations if r['mentor']==s['mentor'] and r['date']==s['date'] and r['status'] not in ["거절됨", "취소됨"])
                if not is_booked:
                    d_str = s['date'].strftime("%m/%d")
                    avail_summary[s['mentor']] = avail_summary.get(s['mentor'], set()) | {d_str}
            
            if not avail_summary: st.write("현재 모든 일정이 마감되었습니다.")
            else:
                for m, dates in avail_summary.items():
                    st.success(f"✅ **{m}** 멘토님 : {', '.join(sorted(list(dates)))} 예약 가능")

    st.markdown("---")

    # [수정] 신청자 정보 4종 세트 한 줄 배치 (성함/직급/팀명/이메일)
    col_info1, col_info2, col_info3, col_info4 = st.columns([1, 1, 1, 2])
    with col_info1: mentee_name = st.text_input("신청자 성함")
    with col_info2: mentee_pos = st.text_input("신청자 직급")
    with col_info3: mentee_team = st.text_input("신청자 팀명")
    with col_info4: mentee_email = st.text_input("사내 이메일 주소")

    st.markdown("<br>", unsafe_allow_html=True) # 미세 여백 조절

    # [수정] 하단 섹션 좌우 분할 (왼쪽: 선택 및 입력 / 오른쪽: 멘토 프로필)
    col_main, col_profile = st.columns([1.2, 1])

    with col_main:
        selected_m = st.selectbox("상담받을 멘토 선택", mentor_names)
        sel_date = st.date_input("희망 날짜 선택", datetime.date.today() + datetime.timedelta(days=1))
        
        slots_found = [s for s in st.session_state.available_slots if s['mentor']==selected_m and s['date']==sel_date]
        if not slots_found:
            if selected_m != "선택해주세요": st.warning("선택하신 날짜에 멘토님의 오픈된 일정이 없습니다.")
        else:
            st.info("📍 멘토가 지정한 장소와 시간을 확인하세요.")
            for s in slots_found:
                loc_txt = s.get('location', '장소 미지정')
                st.write(f"⏰ **{s['start'].strftime('%H:%M')} ~ {s['end'].strftime('%H:%M')}** | 📍 {loc_txt}")
            
            cs, ce = st.columns(2)
            with cs: t_start = st.time_input("시작 시간", slots_found[0]['start'])
            with ce: t_end = st.time_input("종료 시간", slots_found[0]['end'])

        m_topic = st.text_area("사전 질문 및 상담 주제 (필수)", placeholder="멘토링을 통해 얻고 싶은 점을 구체적으로 적어주세요.")

    with col_profile:
        if selected_m != "선택해주세요":
            p_card = next((m for m in st.session_state.mentors_data if m['name'] == selected_m), None)
            if p_card:
                # 멘토 프로필을 오른쪽에 명함 형태로 표시
                st.markdown(f"""
                    <div style="border: 2px solid #4A90E2; padding: 30px; border-radius: 15px; background-color: #f0f7ff; min-height: 400px;">
                        <h3 style="margin-top:0; color: #1E3A8A; border-bottom: 2px solid #4A90E2; padding-bottom: 10px;">🎖️ {p_card['name']} {p_card.get('position','')} 멘토</h3>
                        <p style="font-size: 1.15em; margin-top: 20px;">🏢 <b>소속:</b> {p_card.get('team','정보 없음')}</p>
                        <p style="font-size: 1.15em;">🎯 <b>전문영역:</b> {p_card.get('expertise','정보 없음')}</p>
                        <div style="margin-top: 30px; background-color: white; padding: 20px; border-radius: 10px; border-left: 8px solid #4A90E2;">
                            <p style="font-size: 1.1em; color: #333; line-height: 1.6;"><b>멘토의 한마디:</b><br>
                            <i>"{p_card.get('greeting','열린 마음으로 기다리고 있겠습니다.')}"</i></p>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("위에서 멘토를 선택하시면 상세 정보가 이곳에 나타납니다.")

    if st.button("🚀 멘토링 예약 신청하기", type="primary", use_container_width=True):
        if not mentee_name or selected_m == "선택해주세요" or not m_topic:
            st.error("신청자 정보와 멘토, 상담 주제를 모두 입력해 주세요.")
        else:
            new_res = {
                "id": str(uuid.uuid4()), "mentor": selected_m, "mentee_name": mentee_name, 
                "mentee_position": mentee_pos, "mentee_team": mentee_team, "mentee_email": mentee_email,
                "date": sel_date, "start_time": t_start, "end_time": t_end, "topic": m_topic, "status": "대기중"
            }
            st.session_state.reservations.append(new_res)
            safe_save(ws_res, st.session_state.reservations)
            st.balloons()
            st.success("예약 신청이 완료되었습니다!")

# --- [💼 탭 2: 멘토 일정 관리] ---
with tab2:
    st.subheader("💼 나의 멘토링 일정 및 계정 관리")
    m_login = st.selectbox("본인 성함 선택", mentor_names, key="m_login_t2")
    if m_login != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_login), None)
        if m_info and st.text_input("멘토 비밀번호 입력", type="password", key="m_pw_t2") == str(m_info['pw']):
            
            with st.expander("🔑 내 비밀번호 변경하기"):
                new_pw = st.text_input("새 비밀번호", type="password")
                if st.button("비밀번호 업데이트"):
                    m_info['pw'] = new_pw
                    safe_save(ws_mentors, st.session_state.mentors_data)
                    st.success("비밀번호가 변경되었습니다.")

            st.markdown("#### ✨ 새로운 상담 시간 및 장소 등록")
            c1, c2, c3, c4 = st.columns(4)
            with c1: d_val = st.date_input("날짜", datetime.date.today(), key="d_t2")
            with c2: s_val = st.time_input("시작", datetime.time(13,0), key="s_t2")
            with c3: e_val = st.time_input("종료", datetime.time(17,0), key="e_t2")
            with c4: loc_val = st.text_input("📍 상담 장소")
            
            if st.button("일정 확정 및 등록"):
                st.session_state.available_slots.append({"mentor": m_login, "date": d_val, "start": s_val, "end": e_val, "location": loc_val})
                safe_save(ws_slots, st.session_state.available_slots)
                st.success("새로운 일정이 등록되었습니다.")
                st.rerun()

            st.divider()
            st.markdown("#### 🗑️ 내가 등록한 일정 목록")
            for i, s in enumerate([x for x in st.session_state.available_slots if x['mentor']==m_login]):
                col_a, col_b = st.columns([4,1])
                col_a.write(f"📅 {s['date']} | ⏰ {s['start']}~{s['end']} | 📍 {s.get('location','장소 미지정')}")
                if col_b.button("삭제", key=f"del_s_{i}"):
                    st.session_state.available_slots.remove(s)
                    safe_save(ws_slots, st.session_state.available_slots)
                    st.rerun()

# --- [📋 탭 3: 멘토 예약 관리] ---
with tab3:
    st.subheader("📋 멘티 신청 현황 관리")
    m_sel_t3 = st.selectbox("본인 성함 선택", mentor_names, key="m_sel_t3")
    if m_sel_t3 != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name']==m_sel_t3), None)
        if m_info and st.text_input("비밀번호 확인", type="password", key="pw_t3") == str(m_info['pw']):
            my_res = [r for r in st.session_state.reservations if r['mentor']==m_sel_t3]
            if not my_res: st.info("아직 신청된 내역이 없습니다.")
            for r in my_res:
                with st.expander(f"[{r['status']}] {r['mentee_name']} {r.get('mentee_position','')}님 ({r.get('mentee_team','')})"):
                    st.write(f"⏰ 시간: {r['start_time']} ~ {r['end_time']}")
                    st.write(f"💬 상담 주제: {r['topic']}")
                    if r['status'] == "대기중":
                        ca, cb = st.columns(2)
                        if ca.button("✅ 예약 승인", key=f"ok_{r['id']}"):
                            r['status']="승인됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()
                        if cb.button("❌ 예약 거절", key=f"no_{r['id']}"):
                            r['status']="거절됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()
                    elif r['status'] == "승인됨":
                        if st.button("🚫 예약 취소", key=f"can_{r['id']}"):
                            r['status']="취소됨"; safe_save(ws_res, st.session_state.reservations); st.rerun()

# --- [👑 탭 4: 관리자 메뉴] ---
with tab4:
    st.subheader("👑 인사팀 전용 관리자 시스템")
    if not st.session_state.get("admin_logged_in", False):
        a_id = st.text_input("Admin ID")
        a_pw = st.text_input("Admin PW", type="password")
        if st.button("관리자 로그인"):
            if a_id == st.session_state.admin_info['id'] and a_pw == str(st.session_state.admin_info['pw']):
                st.session_state.admin_logged_in = True; st.rerun()
            else: st.error("로그인 정보가 틀립니다.")
    else:
        if st.button("관리자 로그아웃"): st.session_state.admin_logged_in = False; st.rerun()
        st.divider()
        with st.expander("👨‍🏫 멘토 신규 등록"):
            nc1, nc2, nc3, nc4 = st.columns(4)
            n_m = nc1.text_input("성함")
            n_p_title = nc2.text_input("직급")
            n_t = nc3.text_input("소속 팀명")
            n_pw = nc4.text_input("임시 비번")
            n_e = st.text_input("전문 영역")
            n_em = st.text_input("이메일 주소")
            n_g = st.text_area("멘토 인사말")
            if st.button("멘토 등록하기"):
                st.session_state.mentors_data.append({"name":n_m, "position":n_p_title, "team":n_t, "pw":n_pw, "expertise":n_e, "greeting":n_g, "email":n_em})
                safe_save(ws_mentors, st.session_state.mentors_data)
                st.success("멘토가 등록되었습니다.")
                st.rerun()
        
        with st.expander("📋 등록된 멘토 관리 (수정/삭제)", expanded=True):
            for i, m in enumerate(st.session_state.mentors_data):
                st.markdown(f"**[{m['name']}] 정보 관리**")
                col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1.5])
                u_name = col1.text_input("이름", value=m.get('name',''), key=f"un_{i}")
                u_pos = col2.text_input("직급", value=m.get('position',''), key=f"up_{i}")
                u_team = col3.text_input("팀명", value=m.get('team',''), key=f"ut_{i}")
                u_pw = col4.text_input("비번", value=m.get('pw',''), key=f"upw_{i}")
                u_email = col5.text_input("이메일", value=m.get('email',''), key=f"uem_{i}")
                u_exp = st.text_input("전문영역", value=m.get('expertise',''), key=f"ue_{i}")
                u_greet = st.text_area("인사말", value=m.get('greeting',''), key=f"ug_{i}")
                btn1, btn2 = st.columns([1, 8])
                if btn1.button("💾 저장", key=f"us_{i}"):
                    st.session_state.mentors_data[i].update({"name":u_name, "position":u_pos, "team":u_team, "pw":u_pw, "expertise":u_exp, "greeting":u_greet, "email":u_email})
                    safe_save(ws_mentors, st.session_state.mentors_data)
                    st.success("수정 완료!")
                if btn2.button("❌ 삭제", key=f"ud_{i}"):
                    st.session_state.mentors_data.pop(i)
                    safe_save(ws_mentors, st.session_state.mentors_data)
                    st.rerun()
                st.divider()
