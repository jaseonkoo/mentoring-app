import streamlit as st
import datetime
import uuid
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="사내 멘토링 예약", page_icon="🤝", layout="wide")

# ==========================================
# ☁️ [핵심 1] 구글 스프레드시트 로그인 & 연결
# ==========================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource # 컴퓨터가 로그인 과정을 매번 반복하지 않게 기억해둡니다.
def init_gspread():
    # 1. 아까 이름 바꾼 secrets.json 파일로 로그인합니다.
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    # 2. '멘토링예약DB' 문서를 엽니다.
    doc = client.open("멘토링예약DB")
    
    # 3. 데이터가 저장될 두 개의 탭(워크시트)을 찾습니다. 없으면 자동으로 만듭니다!
    try:
        ws_slots = doc.worksheet("slots")
    except gspread.exceptions.WorksheetNotFound:
        ws_slots = doc.add_worksheet(title="slots", rows="1000", cols="20")
        
    try:
        ws_res = doc.worksheet("reservations")
    except gspread.exceptions.WorksheetNotFound:
        ws_res = doc.add_worksheet(title="reservations", rows="1000", cols="20")
        
    return ws_slots, ws_res

# 봇(Bot) 출입증으로 문서 열기 완료!
ws_slots, ws_res = init_gspread()


# ==========================================
# 💾 [핵심 2] 데이터 불러오기 및 저장하기 함수
# ==========================================
def load_data():
    # 1. 멘토 일정(slots) 불러오기
    try:
        slots_records = ws_slots.get_all_records()
        for r in slots_records:
            r['date'] = datetime.datetime.strptime(str(r['date']), "%Y-%m-%d").date()
            r['start'] = datetime.datetime.strptime(str(r['start']), "%H:%M:%S").time()
            r['end'] = datetime.datetime.strptime(str(r['end']), "%H:%M:%S").time()
        st.session_state.available_slots = slots_records
    except:
        st.session_state.available_slots = []

    # 2. 예약 내역(reservations) 불러오기
    try:
        res_records = ws_res.get_all_records()
        for r in res_records:
            r['date'] = datetime.datetime.strptime(str(r['date']), "%Y-%m-%d").date()
            r['start_time'] = datetime.datetime.strptime(str(r['start_time']), "%H:%M:%S").time()
            r['end_time'] = datetime.datetime.strptime(str(r['end_time']), "%H:%M:%S").time()
        st.session_state.reservations = res_records
    except:
        st.session_state.reservations = []

def save_slots():
    if len(st.session_state.available_slots) > 0:
        df = pd.DataFrame(st.session_state.available_slots)
        df['date'] = df['date'].astype(str)
        df['start'] = df['start'].astype(str)
        df['end'] = df['end'].astype(str)
        # 구글 시트를 싹 지우고 새롭게 업데이트된 표를 덮어씁니다.
        ws_slots.clear()
        ws_slots.update([df.columns.values.tolist()] + df.values.tolist())

def save_reservations():
    if len(st.session_state.reservations) > 0:
        df = pd.DataFrame(st.session_state.reservations)
        df['date'] = df['date'].astype(str)
        df['start_time'] = df['start_time'].astype(str)
        df['end_time'] = df['end_time'].astype(str)
        ws_res.clear()
        ws_res.update([df.columns.values.tolist()] + df.values.tolist())


# 프로그램이 처음 켜질 때 구글에서 데이터를 싹 읽어옵니다.
if "data_loaded" not in st.session_state:
    load_data()
    st.session_state.data_loaded = True


# ==========================================
# 이하 화면 구성 (이전과 똑같이 잘 작동합니다!)
# ==========================================
def send_email(to_email, subject, body):
    st.toast(f"📧 [메일 발송] {to_email}\n제목: {subject}", icon="✉️")

mentors = ["선택해주세요", "김철수 부장", "이영희 차장", "박민수 과장"]
mentor_info = {
    "김철수 부장": {"pw": "1111", "email": "kim@company.kr"},
    "이영희 차장": {"pw": "2222", "email": "lee@company.kr"},
    "박민수 과장": {"pw": "3333", "email": "park@company.kr"}
}

tab1, tab2, tab3 = st.tabs(["🙋‍♂️ 멘티 예약 신청", "💼 멘토 일정 등록", "📋 멘토 예약 관리 (승인)"])

# 탭 3: 예약 관리 (승인)
with tab3:
    st.subheader("📋 멘토 예약 현황 및 승인")
    mentor_name_tab3 = st.selectbox("본인(멘토) 이름 선택", mentors, key="mentor_select_tab3")
    
    if mentor_name_tab3 != "선택해주세요":
        input_pw_tab3 = st.text_input("비밀번호 4자리 입력", type="password", key="pw_tab3")
        
        if input_pw_tab3 == mentor_info[mentor_name_tab3]["pw"]:
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
                                    save_reservations() # ☁️ 구글 시트에 바로 동기화!
                                    send_email(res['mentee_email'], "[멘토링 확정] 예약이 승인되었습니다.", "상담이 확정되었습니다.")
                                    send_email(mentor_info[mentor_name_tab3]["email"], "[일정 확정] 멘토링 확정", "내 일정에 추가되었습니다.")
                                    st.rerun()
                            with col_btn2:
                                if st.button("❌ 거절", key=f"rej_{res['id']}"):
                                    res['status'] = "거절됨"
                                    save_reservations() # ☁️ 구글 시트에 바로 동기화!
                                    send_email(res['mentee_email'], "[멘토링 안내] 예약이 거절되었습니다.", "다른 일정을 선택해주세요.")
                                    st.rerun()
                        st.markdown("---")
        elif input_pw_tab3 != "":
            st.error("비밀번호가 틀렸습니다.")

# 탭 2: 멘토 일정 등록
with tab2:
    st.subheader("💼 멘토 일정 등록 (예약 가능 시간 열기)")
    mentor_name_tab2 = st.selectbox("본인(멘토) 이름 선택", mentors, key="mentor_select_tab2")
    
    if mentor_name_tab2 != "선택해주세요":
        input_pw_tab2 = st.text_input("비밀번호 4자리", type="password", key="pw_tab2")
        
        if input_pw_tab2 == mentor_info[mentor_name_tab2]["pw"]:
            col_date, col_start, col_end = st.columns(3)
            with col_date:
                avail_date = st.date_input("상담 가능한 날짜", datetime.date.today())
            with col_start:
                start_time = st.time_input("오픈 시작 시간", datetime.time(13, 0))
            with col_end:
                end_time = st.time_input("오픈 종료 시간", datetime.time(17, 0))
                
            if st.button("✅ 이 시간 예약 가능으로 열기"):
                if start_time >= end_time:
                    st.error("⚠️ 종료 시간은 시작 시간보다 늦어야 합니다!")
                else:
                    slot_info = {"mentor": mentor_name_tab2, "date": avail_date, "start": start_time, "end": end_time}
                    if slot_info not in st.session_state.available_slots:
                        st.session_state.available_slots.append(slot_info)
                        save_slots() # ☁️ 구글 시트에 바로 동기화!
                        st.success(f"{avail_date} 일정이 성공적으로 추가되었습니다!")
                    else:
                        st.warning("이미 등록된 시간입니다.")

            st.write("---")
            st.write(f"**[{mentor_name_tab2}] 님이 열어둔 일정**")
            for slot in st.session_state.available_slots:
                if slot["mentor"] == mentor_name_tab2:
                    st.write(f"- 📅 {slot['date']} ⏰ {slot['start'].strftime('%H:%M')} ~ {slot['end'].strftime('%H:%M')}")
        elif input_pw_tab2 != "":
            st.error("비밀번호가 틀렸습니다.")

# 탭 1: 멘티 예약 신청
with tab1:
    st.subheader("🙋‍♂️ 원하시는 멘토와 시간을 선택해 주세요.")
    
    st.markdown("##### 📢 [안내] 현재 예약 가능한 멘토 일정")
    if len(st.session_state.available_slots) == 0:
        st.info("현재 열려있는 멘토링 일정이 없습니다. 멘토가 일정을 등록할 때까지 기다려주세요.")
    else:
        summary = {}
        for slot in st.session_state.available_slots:
            m_name = slot["mentor"]
            d_str = slot["date"].strftime("%m월 %d일")
            if m_name not in summary:
                summary[m_name] = set()
            summary[m_name].add(d_str)
        
        for m_name, dates in summary.items():
            st.success(f"**{m_name}** : {', '.join(sorted(list(dates)))} 오픈됨")
    st.markdown("---")
    
    mentee_name = st.text_input("신청자(멘티) 이름")
    mentee_email = st.text_input("신청자 이메일 주소")
    selected_mentor = st.selectbox("1. 멘토 선택", mentors, key="mentee_select")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_date = st.date_input("2. 희망 날짜 선택 (위 안내판을 참고하세요!)", datetime.date.today() + datetime.timedelta(days=1), key="mentee_date")
        
    with col2:
        available_blocks = [s for s in st.session_state.available_slots if s["mentor"] == selected_mentor and s["date"] == selected_date]
                
        if len(available_blocks) == 0:
            st.error("선택하신 멘토는 이 날짜에 상담 가능한 시간이 없습니다.")
            mentee_start = None
            mentee_end = None
        else:
            st.info("✅ 아래 멘토의 가능 시간 안에서 원하는 상담 시간을 입력하세요.")
            for b in available_blocks:
                st.write(f"▶ 멘토 오픈 시간: **{b['start'].strftime('%H:%M')} ~ {b['end'].strftime('%H:%M')}**")
            
            col_s, col_e = st.columns(2)
            with col_s:
                mentee_start = st.time_input("3. 상담 시작 시간", available_blocks[0]['start'], key="m_start")
            with col_e:
                mentee_end = st.time_input("4. 상담 종료 시간", available_blocks[0]['end'], key="m_end")

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
                    if res['mentor'] == selected_mentor and res['date'] == selected_date and res['status'] != "거절됨":
                        if max(mentee_start, res['start_time']) < min(mentee_end, res['end_time']):
                            overlap = True
                            break
                
                if overlap:
                    st.error("🚫 죄송합니다. 선택하신 시간에 이미 다른 분의 예약이 존재합니다. 다른 시간을 선택해주세요.")
                else:
                    new_reservation = {
                        "id": str(uuid.uuid4()),
                        "mentor": selected_mentor,
                        "mentee_name": mentee_name,
                        "mentee_email": mentee_email,
                        "date": selected_date,
                        "start_time": mentee_start,
                        "end_time": mentee_end,
                        "topic": mentoring_topic,
                        "status": "대기중"
                    }
                    st.session_state.reservations.append(new_reservation)
                    save_reservations() # ☁️ 구글 시트에 바로 동기화!
                    
                    st.success("🎉 예약 신청이 완료되었습니다! 멘토의 승인을 기다려주세요.")
                    send_email(mentor_info[selected_mentor]["email"], f"[신규 예약] {mentee_name}님", "새로운 신청 확인 요망")

