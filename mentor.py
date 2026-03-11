import streamlit as st
import datetime
import uuid
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 브라우저 탭 이름 변경
st.set_page_config(page_title="Daehan Feed Mentoring", page_icon="🤝", layout="wide")

# ==========================================
# 🪄 관리자 로그인 시에만 상단 메뉴 보이기
# ==========================================
if not st.session_state.get("admin_logged_in", False):
    hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
    """
    st.markdown(hide_menu_style, unsafe_allow_html=True)

# 메인 타이틀 달기
st.title("🤝 Daehan Feed Mentoring")
st.markdown("---")

# ==========================================
# ☁️ [핵심 1] 구글 스프레드시트 연결 및 탭 생성
# ==========================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def init_gspread():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    doc = client.open("멘토링예약DB")
    
    try: ws_slots = doc.worksheet("slots")
    except: ws_slots = doc.add_worksheet(title="slots", rows="1000", cols="20")
        
    try: ws_res = doc.worksheet("reservations")
    except: ws_res = doc.add_worksheet(title="reservations", rows="1000", cols="20")
        
    try: ws_mentors = doc.worksheet("mentors")
    except: ws_mentors = doc.add_worksheet(title="mentors", rows="100", cols="10") 
        
    try: ws_admin = doc.worksheet("admin")
    except: ws_admin = doc.add_worksheet(title="admin", rows="10", cols="2")
        
    return ws_slots, ws_res, ws_mentors, ws_admin

ws_slots, ws_res, ws_mentors, ws_admin = init_gspread()

# ==========================================
# 💾 [핵심 2] 데이터 불러오기 및 저장 함수
# ==========================================
def load_data():
    try:
        admin_records = ws_admin.get_all_records()
        if admin_records:
            st.session_state.admin_info = admin_records[0]
        else:
            st.session_state.admin_info = {"id": "admin", "pw": "dhfeed1947"}
    except:
        st.session_state.admin_info = {"id": "admin", "pw": "dhfeed1947"}

    try:
        st.session_state.mentors_data = ws_mentors.get_all_records()
    except:
        st.session_state.mentors_data = []

    try:
        slots_records = ws_slots.get_all_records()
        for r in slots_records:
            r['date'] = datetime.datetime.strptime(str(r['date']), "%Y-%m-%d").date()
            r['start'] = datetime.datetime.strptime(str(r['start']), "%H:%M:%S").time()
            r['end'] = datetime.datetime.strptime(str(r['end']), "%H:%M:%S").time()
        st.session_state.available_slots = slots_records
    except:
        st.session_state.available_slots = []

    try:
        res_records = ws_res.get_all_records()
        for r in res_records:
            r['date'] = datetime.datetime.strptime(str(r['date']), "%Y-%m-%d").date()
            r['start_time'] = datetime.datetime.strptime(str(r['start_time']), "%H:%M:%S").time()
            r['end_time'] = datetime.datetime.strptime(str(r['end_time']), "%H:%M:%S").time()
        st.session_state.reservations = res_records
    except:
        st.session_state.reservations = []

def save_admin():
    df = pd.DataFrame([st.session_state.admin_info])
    df = df.fillna("")
    ws_admin.clear()
    ws_admin.update([df.columns.values.tolist()] + df.values.tolist())

def save_mentors():
    ws_mentors.clear()
    if st.session_state.mentors_data:
        df = pd.DataFrame(st.session_state.mentors_data)
        df = df.fillna("") 
        ws_mentors.update([df.columns.values.tolist()] + df.values.tolist())

def save_slots():
    ws_slots.clear()
    if len(st.session_state.available_slots) > 0:
        df = pd.DataFrame(st.session_state.available_slots)
        df['date'] = df['date'].astype(str)
        df['start'] = df['start'].astype(str)
        df['end'] = df['end'].astype(str)
        df = df.fillna("")
        ws_slots.update([df.columns.values.tolist()] + df.values.tolist())

def save_reservations():
    ws_res.clear()
    if len(st.session_state.reservations) > 0:
        df = pd.DataFrame(st.session_state.reservations)
        df['date'] = df['date'].astype(str)
        df['start_time'] = df['start_time'].astype(str)
        df['end_time'] = df['end_time'].astype(str)
        df = df.fillna("")
        ws_res.update([df.columns.values.tolist()] + df.values.tolist())

if "data_loaded" not in st.session_state:
    load_data()
    st.session_state.data_loaded = True

def send_email(to_email, subject, body):
    st.toast(f"📧 [메일 발송] {to_email}\n제목: {subject}", icon="✉️")

mentor_names_list = ["선택해주세요"] + [m['name'] for m in st.session_state.mentors_data]

# ==========================================
# 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 관리", "📋 멘토 예약 관리", "👑 관리자 메뉴"])

# ==========================================
# 👑 탭 4: 관리자 메뉴
# ==========================================
with tab4:
    st.subheader("👑 시스템 관리자 메뉴")
    
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        admin_id = st.text_input("관리자 아이디")
        admin_pw = st.text_input("관리자 비밀번호", type="password")
        if st.button("로그인", key="admin_login"):
            if admin_id == st.session_state.admin_info["id"] and admin_pw == str(st.session_state.admin_info["pw"]):
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 틀렸습니다.")
    else:
        st.success("✅ 관리자로 로그인되었습니다.")
        if st.button("로그아웃"):
            st.session_state.admin_logged_in = False
            st.rerun()
            
        st.markdown("---")
        
        with st.expander("🔑 관리자 비밀번호 변경", expanded=False):
            new_admin_pw = st.text_input("새 관리자 비밀번호", type="password")
            if st.button("관리자 비밀번호 업데이트"):
                if new_admin_pw:
                    st.session_state.admin_info["pw"] = new_admin_pw
                    save_admin()
                    st.success("관리자 비밀번호가 성공적으로 변경되었습니다!")
                else:
                    st.warning("비밀번호를 입력해주세요.")
                    
        with st.expander("👨‍🏫 신규 멘토 등록", expanded=True):
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1: new_m_name = st.text_input("멘토 이름 (예: 홍길동 부장)")
            with col_m2: new_m_team = st.text_input("소속 팀명 (예: 인사총무팀)")
            with col_m3: new_m_pw = st.text_input("초기 비밀번호 (숫자 등)")
            
            col_m4, col_m5 = st.columns([1, 2])
            with col_m4: new_m_expertise = st.text_input("전문 영역 (예: 조직문화, 커리어)")
            with col_m5: new_m_email = st.text_input("멘토 이메일")
            
            new_m_greeting = st.text_area("멘토 인사말 (멘티들에게 전하는 짧은 환영사)")
            
            if st.button("새 멘토 추가하기"):
                if new_m_name and new_m_pw:
                    if any(m['name'] == new_m_name for m in st.session_state.mentors_data):
                        st.error("이미 등록된 멘토 이름입니다.")
                    else:
                        st.session_state.mentors_data.append({
                            "name": new_m_name, 
                            "pw": str(new_m_pw), 
                            "email": new_m_email,
                            "team": new_m_team,
                            "expertise": new_m_expertise,
                            "greeting": new_m_greeting
                        })
                        save_mentors()
                        st.success(f"'{new_m_name}' 멘토가 완벽하게 등록되었습니다!")
                        st.rerun()
                else:
                    st.warning("이름과 비밀번호는 필수입니다.")

        with st.expander("📋 등록된 멘토 관리 (정보 수정 및 삭제)", expanded=True):
            if not st.session_state.mentors_data:
                st.info("등록된 멘토가 없습니다.")
            else:
                for i, m in enumerate(st.session_state.mentors_data):
                    st.markdown(f"**[{m['name']}] 멘토 정보 수정**")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1: update_pw = st.text_input("비번 변경", value=m.get('pw', ''), key=f"pw_{i}", type="password")
                    with c2: update_team = st.text_input("팀명", value=m.get('team', ''), key=f"team_{i}")
                    with c3: update_exp = st.text_input("전문영역", value=m.get('expertise', ''), key=f"exp_{i}")
                    
                    c4, c5 = st.columns([1, 2])
                    with c4: update_email = st.text_input("이메일", value=m.get('email', ''), key=f"em_{i}")
                    with c5: update_greet = st.text_input("인사말", value=m.get('greeting', ''), key=f"greet_{i}")
                    
                    btn1, btn2 = st.columns([1, 10])
                    with btn1:
                        if st.button("💾 저장", key=f"save_m_{i}"):
                            st.session_state.mentors_data[i]['pw'] = str(update_pw)
                            st.session_state.mentors_data[i]['team'] = update_team
                            st.session_state.mentors_data[i]['expertise'] = update_exp
                            st.session_state.mentors_data[i]['email'] = update_email
                            st.session_state.mentors_data[i]['greeting'] = update_greet
                            save_mentors()
                            st.success("정보가 성공적으로 수정되었습니다!")
                    with btn2:        
                        if st.button("❌ 삭제", key=f"del_m_{i}"):
                            deleted_name = st.session_state.mentors_data[i]['name']
                            st.session_state.mentors_data.pop(i)
                            save_mentors()
                            st.session_state.available_slots = [s for s in st.session_state.available_slots if s["mentor"] != deleted_name]
                            save_slots()
                            st.session_state.reservations = [r for r in st.session_state.reservations if r["mentor"] != deleted_name]
                            save_reservations()
                            st.rerun()
                    st.divider()

# ==========================================
# 💼 탭 2: 멘토 일정 관리
# ==========================================
with tab2:
    st.subheader("💼 멘토 일정 관리 (등록 및 삭제)")
    mentor_name_tab2 = st.selectbox("본인(멘토) 이름 선택", mentor_names_list, key="mentor_select_tab2")
    
    if mentor_name_tab2 != "선택해주세요":
        current_mentor = next((m for m in st.session_state.mentors_data if m["name"] == mentor_name_tab2), None)
        
        if current_mentor:
            input_pw_tab2 = st.text_input("비밀번호 입력", type="password", key="pw_tab2")
            
            if input_pw_tab2 == str(current_mentor["pw"]):
                st.success(f"{mentor_name_tab2}님, 환영합니다!")
                
                # [업데이트 1] 멘토가 스스로 비밀번호를 변경할 수 있는 메뉴
                with st.expander("🔑 내 비밀번호 변경", expanded=False):
                    new_mentor_pw = st.text_input("새로운 비밀번호 입력", type="password", key="new_pw_mentor")
                    if st.button("비밀번호 변경하기"):
                        if new_mentor_pw:
                            for i, m in enumerate(st.session_state.mentors_data):
                                if m['name'] == mentor_name_tab2:
                                    st.session_state.mentors_data[i]['pw'] = str(new_mentor_pw)
                                    break
                            save_mentors()
                            st.success("비밀번호가 안전하게 변경되었습니다!")
                        else:
                            st.warning("새로운 비밀번호를 입력해주세요.")
                
                st.markdown("---")
                
                st.markdown("#### ✨ 새로운 상담 시간 열기")
                col_date, col_start, col_end = st.columns(3)
                with col_date: avail_date = st.date_input("상담 가능한 날짜", datetime.date.today())
                with col_start: start_time = st.time_input("오픈 시작 시간", datetime.time(13, 0))
                with col_end: end_time = st.time_input("오픈 종료 시간", datetime.time(17, 0))
                
                # [업데이트 2] 장소 입력 칸 추가
                slot_location = st.text_input("📍 상담 장소 (예: 인천 본사 회의실, 온라인 화상회의 등)")
                    
                if st.button("✅ 이 시간 예약 가능으로 열기"):
                    if start_time >= end_time:
                        st.error("⚠️ 종료 시간은 시작 시간보다 늦어야 합니다!")
                    else:
                        slot_info = {
                            "mentor": mentor_name_tab2, 
                            "date": avail_date, 
                            "start": start_time, 
                            "end": end_time,
                            "location": slot_location # 장소 정보 추가!
                        }
                        if slot_info not in st.session_state.available_slots:
                            st.session_state.available_slots.append(slot_info)
                            save_slots() 
                            st.success(f"{avail_date} 일정이 성공적으로 추가되었습니다!")
                            st.rerun()
                        else:
                            st.warning("이미 등록된 시간입니다.")

                st.markdown("---")
                
                st.markdown("#### 🗑️ 내가 열어둔 일정 관리")
                st.caption("※ 일정을 수정하려면 기존 일정을 [삭제]한 뒤 새로 [추가]해 주세요.")
                
                my_slots = [s for s in st.session_state.available_slots if s["mentor"] == mentor_name_tab2]
                
                if not my_slots:
                    st.info("등록해둔 일정이 없습니다.")
                else:
                    for i, slot in enumerate(my_slots):
                        col_info, col_btn = st.columns([4, 1])
                        with col_info:
                            # [업데이트 2] 관리 화면에서도 장소가 보이도록 수정
                            display_loc = slot.get('location', '장소 미지정')
                            st.write(f"📅 **{slot['date']}** ⏰ {slot['start'].strftime('%H:%M')} ~ {slot['end'].strftime('%H:%M')} | 📍 {display_loc}")
                        with col_btn:
                            if st.button("❌ 삭제", key=f"del_slot_{slot['date']}_{slot['start']}"):
                                st.session_state.available_slots.remove(slot)
                                save_slots()
                                st.success("일정이 삭제되었습니다.")
                                st.rerun()
                        st.divider()
                        
            elif input_pw_tab2 != "":
                st.error("비밀번호가 틀렸습니다.")

# ==========================================
# 📋 탭 3: 멘토 예약 관리
# ==========================================
with tab3:
    st.subheader("📋 멘토 예약 현황 및 관리")
    mentor_name_tab3 = st.selectbox("본인(멘토) 이름 선택", mentor_names_list, key="mentor_select_tab3")
    
    if mentor_name_tab3 != "선택해주세요":
        current_mentor = next((m for m in st.session_state.mentors_data if m["name"] == mentor_name_tab3), None)
        if current_mentor:
            input_pw_tab3 = st.text_input("비밀번호 입력", type="password", key="pw_tab3")
            
            if input_pw_tab3 == str(current_mentor["pw"]):
                st.success(f"{mentor_name_tab3}님의 예약 관리 화면입니다.")
                st.markdown("---")
                
                my_reservations = [r for r in st.session_state.reservations if r["mentor"] == mentor_name_tab3]
                
                if not my_reservations:
                    st.write("현재 들어온 예약 신청이 없습니다.")
                else:
                    for res in my_reservations:
                        with st.container():
                            st.write(f"**[{res['status']}] 📅 {res['date']} ⏰ {res['start_time'].strftime('%H:%M')} ~ {res['end_time'].strftime('%H:%M')}**")
                            st.write(f"- **신청자:** {res['mentee_name']} ({res['mentee_email']})")
                            st.write(f"- **사전 질문:** {res['topic']}")
                            
                            if res['status'] == "대기중":
                                col_btn1, col_btn2 = st.columns([1, 10])
                                with col_btn1:
                                    if st.button("✅ 승인", key=f"app_{res['id']}"):
                                        res['status'] = "승인됨"
                                        save_reservations() 
                                        send_email(res['mentee_email'], "[멘토링 확정] 예약 승인", "상담이 확정되었습니다.")
                                        st.rerun()
                                with col_btn2:
                                    if st.button("❌ 거절", key=f"rej_{res['id']}"):
                                        res['status'] = "거절됨"
                                        save_reservations() 
                                        st.rerun()
                            elif res['status'] == "승인됨":
                                if st.button("🚫 예약 취소", key=f"cancel_{res['id']}"):
                                    res['status'] = "취소됨"
                                    save_reservations() 
                                    st.rerun()
                            st.markdown("---")
            elif input_pw_tab3 != "":
                st.error("비밀번호가 틀렸습니다.")

# ==========================================
# 🙋‍♂️ 탭 1: 멘티 예약 신청
# ==========================================
with tab1:
    st.subheader("🙋‍♂️ 원하시는 멘토와 시간을 선택해 주세요.")
    
    st.markdown("##### 📢 [안내] 현재 예약 가능한 멘토 일정")
    if len(st.session_state.available_slots) == 0:
        st.info("현재 열려있는 멘토링 일정이 없습니다. 멘토가 일정을 등록할 때까지 기다려주세요.")
    else:
        avail_dict = {}
        for slot in st.session_state.available_slots:
            key = (slot["mentor"], slot["date"])
            dummy = datetime.date(2000, 1, 1)
            s_dt = datetime.datetime.combine(dummy, slot["start"])
            e_dt = datetime.datetime.combine(dummy, slot["end"])
            avail_dict[key] = avail_dict.get(key, 0) + (e_dt - s_dt).total_seconds() / 60.0
            
        booked_dict = {}
        for res in st.session_state.reservations:
            if res["status"] not in ["거절됨", "취소됨"]:
                key = (res["mentor"], res["date"])
                dummy = datetime.date(2000, 1, 1)
                s_dt = datetime.datetime.combine(dummy, res["start_time"])
                e_dt = datetime.datetime.combine(dummy, res["end_time"])
                booked_dict[key] = booked_dict.get(key, 0) + (e_dt - s_dt).total_seconds() / 60.0

        summary = {}
        for (m_name, d_obj), total_avail in avail_dict.items():
            total_booked = booked_dict.get((m_name, d_obj), 0)
            if total_avail > total_booked:
                d_str = d_obj.strftime("%m월 %d일")
                if m_name not in summary: summary[m_name] = set()
                summary[m_name].add(d_str)
        
        if not summary:
            st.info("현재 모든 멘토의 일정이 예약 마감되었습니다. 다음 일정을 기다려주세요.")
        else:
            for m_name, dates in summary.items():
                st.success(f"**{m_name}** : {', '.join(sorted(list(dates)))} 예약 가능")
    st.markdown("---")
    
    mentee_name = st.text_input("신청자(멘티) 이름")
    mentee_email = st.text_input("신청자 이메일 주소")
    selected_mentor = st.selectbox("1. 멘토 선택", mentor_names_list, key="mentee_select")
    
    if selected_mentor != "선택해주세요":
        m_info = next((m for m in st.session_state.mentors_data if m['name'] == selected_mentor), None)
        if m_info:
            st.markdown("---")
            st.markdown(f"#### 🏷️ 멘토 프로필: **{m_info['name']}**")
            
            t_name = m_info.get('team', '')
            t_exp = m_info.get('expertise', '')
            t_greet = m_info.get('greeting', '')
            
            if t_name or t_exp:
                st.write(f"🏢 **소속:** {t_name if t_name else '미입력'} | 🎯 **전문 영역:** {t_exp if t_exp else '미입력'}")
            if t_greet:
                st.info(f"💡 **멘토의 한마디:**\n\n{t_greet}")
            st.markdown("---")
            
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        selected_date = st.date_input("2. 희망 날짜 선택 (위 안내판 참고)", datetime.date.today() + datetime.timedelta(days=1), key="mentee_date")
        
    with col_right:
        available_blocks = [s for s in st.session_state.available_slots if s["mentor"] == selected_mentor and s["date"] == selected_date]
                
        if len(available_blocks) == 0:
            if selected_mentor != "선택해주세요":
                st.error("선택하신 멘토는 이 날짜에 상담 가능한 시간이 없습니다.")
            mentee_start = None
            mentee_end = None
        else:
            st.info("✅ 아래 멘토의 전체 오픈 시간 안에서 원하는 상담 시간을 입력하세요.")
            for b in available_blocks:
                # [업데이트 2] 멘티 화면에서도 장소를 보여줍니다. (과거 데이터는 '장소 미지정'으로 처리)
                display_loc = b.get('location', '장소 미지정')
                if display_loc == "": display_loc = "장소 미지정"
                
                st.write(f"▶ 멘토 오픈 시간: **{b['start'].strftime('%H:%M')} ~ {b['end'].strftime('%H:%M')}** | 📍 장소: **{display_loc}**")
            
            booked_times = [r for r in st.session_state.reservations if r['mentor'] == selected_mentor and r['date'] == selected_date and r['status'] not in ["거절됨", "취소됨"]]
            
            if booked_times:
                st.warning("🚨 주의: 아래 시간은 이미 예약이 꽉 찼습니다! 피해서 선택해주세요.")
                for r in booked_times:
                    st.write(f"❌ 예약 불가 시간: **{r['start_time'].strftime('%H:%M')} ~ {r['end_time'].strftime('%H:%M')}** (상태: {r['status']})")
            
            col_s, col_e = st.columns(2)
            with col_s: mentee_start = st.time_input("3. 상담 시작 시간", available_blocks[0]['start'], key="m_start")
            with col_e: mentee_end = st.time_input("4. 상담 종료 시간", available_blocks[0]['end'], key="m_end")

    mentoring_topic = st.text_area("5. 멘토링 사전 질문 (필수)", placeholder="어떤 조언이 필요하신가요?")
    st.markdown("---")

    if st.button("예약 신청하기", type="primary"): 
        if not mentee_name or not mentee_email or not mentoring_topic:
            st.warning("⚠️ 이름, 이메일, 사전 질문을 모두 입력해주세요!")
        elif selected_mentor == "선택해주세요" or mentee_start is None:
            st.warning("⚠️ 멘토와 시간을 정확히 선택해주세요!")
        elif mentee_start >= mentee_end:
            st.error("⚠️ 종료 시간은 시작 시간보다 늦어야 합니다!")
        else:
            is_valid_time = False
            for b in available_blocks:
                if mentee_start >= b['start'] and mentee_end <= b['end']:
                    is_valid_time = True
                    break
            
            if not is_valid_time:
                st.error("⚠️ 선택하신 시간이 멘토가 등록한 가능 시간을 벗어났습니다. 시간을 다시 확인해주세요.")
            else:
                overlap = False
                for res in st.session_state.reservations:
                    if res['mentor'] == selected_mentor and res['date'] == selected_date and res['status'] not in ["거절됨", "취소됨"]:
                        if max(mentee_start, res['start_time']) < min(mentee_end, res['end_time']):
                            overlap = True
                            break
                
                if overlap:
                    st.error("🚫 죄송합니다. 선택하신 시간에 이미 다른 분의 예약이 존재합니다. 다른 시간을 선택해주세요.")
                else:
                    new_reservation = {
                        "id": str(uuid.uuid4()), "mentor": selected_mentor, "mentee_name": mentee_name,
                        "mentee_email": mentee_email, "date": selected_date, "start_time": mentee_start,
                        "end_time": mentee_end, "topic": mentoring_topic, "status": "대기중"
                    }
                    st.session_state.reservations.append(new_reservation)
                    save_reservations() 
                    st.success("🎉 예약 신청이 완료되었습니다! 멘토의 승인을 기다려주세요.")
