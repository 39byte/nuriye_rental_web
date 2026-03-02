import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import database as db # 구글 시트(gs) 대신 데이터베이스(db) 모듈 사용

# [PWA/Base Settings] 앱 설정
st.set_page_config(page_title="누리예 카메라 대여 시스템", page_icon="📸", layout="wide", initial_sidebar_state="collapsed")

# [STYLE] CSS 로드 및 테마 전환 로직
theme_mode = st.sidebar.selectbox("테마 선택", ["시스템 설정", "라이트", "다크"], index=0)

# 테마별 색상 팔레트 (순수 색상 변수만 관리)
THEMES = {
    "light": {
        "bg": "#FFFFFF", "text": "#000000", "cont": "#FFFFFF", "input": "#FFFFFF", "brd": "#cccccc",
        "cal_h": "#fdfdfd", "cal_d": "#FFFFFF", "cal_e": "#fdfdfd", "brand": "#B2DFDB", "btn_t": "#FFFFFF"
    },
    "dark": {
        "bg": "#252526", "text": "#E0E0E0", "cont": "#2D2D2D", "input": "#3C3C3C", "brd": "#454545",
        "cal_h": "#333333", "cal_d": "#2D2D2D", "cal_e": "#252526", "brand": "#004246", "btn_t": "#FFFFFF"
    }
}

def get_theme_css(base):
    return f"""
        --bg-color: {base['bg']}; --text-color: {base['text']}; --container-bg: {base['cont']};
        --input-bg: {base['input']}; --border-color: {base['brd']}; --calendar-header-bg: {base['cal_h']};
        --calendar-day-bg: {base['cal_d']}; --calendar-empty-bg: {base['cal_e']};
        --main-brand-color: {base['brand']}; --button-text: {base['btn_t']};
    """

dark_extra = ".rental-line { border: 1px solid rgba(255,255,255,0.2); filter: saturate(1.2) brightness(1.1); } .calendar-day.empty { background-color: var(--calendar-empty-bg) !important; }"

if theme_mode == "시스템 설정":
    dynamic_css = f":root {{ {get_theme_css(THEMES['light'])} }} @media (prefers-color-scheme: dark) {{ :root {{ {get_theme_css(THEMES['dark'])} }} {dark_extra} }}"
elif theme_mode == "라이트":
    dynamic_css = f":root {{ {get_theme_css(THEMES['light'])} }}"
else:
    dynamic_css = f":root {{ {get_theme_css(THEMES['dark'])} }} {dark_extra}"

try:
    with open('style.css', encoding='utf-8') as f:
        st.markdown(f"<style>{f.read()}{dynamic_css}</style>", unsafe_allow_html=True)
except Exception: pass

# 설정 및 데이터 로드 (db 모듈 활용)
settings = db.get_settings()
ADMIN_PASSWORD = settings.get("admin_password", "1111")
STAFF_LIST = ["김지원(암실부장)", "유재동(회장)", "한지원(부회장)", "심종율(총무)", "이서윤(홍보부장)", "김기연(홍보차장)", "김예은(홍보차장)"]

# --- 유틸리티: 캘린더 엔진 (VS Code 보정 반영) ---
def get_calendar_html(rentals, view_year, view_month, is_admin=False):
    """동적 캘린더 생성 (요일 동기화 및 보안 적용)"""
    today = date.today()
    calendar.setfirstweekday(calendar.SUNDAY) # 2026-02-01 일요일 일치 보정
    cal = calendar.monthcalendar(view_year, view_month)
    
    html = f'<div class="calendar-container"><div class="calendar-grid">'
    days = ["일", "월", "화", "수", "목", "금", "토"]
    for d in days: html += f'<div class="calendar-header">{d}</div>'
    
    colors = ["#FF5252", "#448AFF", "#4CAF50", "#FFC107", "#9C27B0", "#00BCD4", "#E91E63"]
    
    for week in cal:
        for day in week:
            if day == 0: html += '<div class="calendar-day empty"></div>'
            else:
                day_date = date(view_year, view_month, day)
                is_today = "today" if day_date == today else ""
                html += f'<div class="calendar-day {is_today}"><b>{day}</b>'
                
                day_rentals = []
                for _, row in rentals.iterrows():
                    try:
                        s = pd.to_datetime(str(row['대여시작일'])).date()
                        e = pd.to_datetime(str(row['반납예정일'])).date()
                        if s <= day_date <= e and str(row['상태']).strip() in ['확정', '대여중']:
                            day_rentals.append(row)
                    except: continue
                
                for i, r in enumerate(day_rentals[:3]):
                    color = colors[i % len(colors)]
                    hist = str(r['전체이력저장'])
                    acc = hist.split("|")[0].replace("액세서리: ", "") if "액세서리: " in hist else "없음"
                    
                    # [DATA_PRIVACY] '비고' 노출 차단 (is_admin=False 일 때)
                    rem_info = f" | 비고: {r['비고']}" if is_admin and r.get('비고') else ""
                    tooltip = f"{r['신청자']} / {r['장비명']} / {acc}{rem_info}"
                    html += f'<div class="rental-line" style="background: {color};" data-tooltip="{tooltip}"></div>'
                
                if len(day_rentals) > 3: html += f'<div style="font-size: 0.6rem; font-weight: bold;">+ {len(day_rentals)-3}건</div>'
                html += '</div>'
    html += '</div></div>'
    return html

# --- 공통 내비게이션 ---
page = st.sidebar.selectbox("메뉴 선택", ["📸 대여 신청 및 현황", "🛠️ 집행부 전용 관리"], key="nav")
if st.sidebar.button("데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

# --- 1. 부원용 신청/현황 ---
if page == "📸 대여 신청 및 현황":
    st.title("📸 누리예 카메라 대여 시스템")
    if 'vy' not in st.session_state: st.session_state.vy = date.today().year
    if 'vm' not in st.session_state: st.session_state.vm = date.today().month

    inventory = db.get_inventory()
    rentals = db.get_rentals()

    col_l, col_r = st.columns([7, 5], gap="large")

    with col_l:
        n1, n2, n3 = st.columns([1, 5, 1])
        with n1:
            if st.button("◀", key="p_m"):
                if st.session_state.vm == 1: st.session_state.vm = 12; st.session_state.vy -= 1
                else: st.session_state.vm -= 1
                st.rerun()
        with n2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.vy}년 {st.session_state.vm}월 대여 현황</h3>", unsafe_allow_html=True)
        with n3:
            if st.button("▶", key="n_m"):
                if st.session_state.vm == 12: st.session_state.vm = 1; st.session_state.vy += 1
                else: st.session_state.vm += 1
                st.rerun()
        st.markdown(get_calendar_html(rentals, st.session_state.vy, st.session_state.vm, is_admin=False), unsafe_allow_html=True)

    with col_r:
        st.subheader("카메라/렌즈 대여 신청")
        
        # [OPTIMIZATION] st.fragment 적용: 양식 내부만 리런되도록 설정
        @st.fragment
        def render_rental_form(inventory):
            if inventory.empty: 
                st.error("장비 정보를 불러올 수 없습니다.")
                return

            # 바디 선택 (Category -> Model)
            b_cats = ["선택 안 함"] + inventory[inventory['구분'] == 'Body']['카테고리'].unique().tolist()
            sel_cat = st.selectbox("1. 바디 카테고리 선택", b_cats)
            
            mods_df = inventory[(inventory['구분'] == 'Body') & (inventory['카테고리'] == sel_cat)]
            sel_mod = st.selectbox("2. 바디 모델 선택", mods_df['모델명'].unique().tolist() if not mods_df.empty else [], index=None, placeholder="바디 미선택 시 렌즈만 대여 가능")
            
            # 유연한 렌즈 필터링
            lenses_df = inventory[(inventory['구분'] == 'Lens') & (inventory['상태'] == '대여가능')]
            
            if sel_mod:
                b_info = mods_df[mods_df['모델명'] == sel_mod].iloc[0]
                b_brand = str(b_info['브랜드']).strip()
                b_spec = str(b_info['규격']).strip() # FF or Crop

                compat_brands = [b_brand]
                if b_brand == "Canon": compat_brands.append("Tamron")
                lenses_df = lenses_df[lenses_df['브랜드'].isin(compat_brands)]
                
                if b_spec == "FF":
                    lenses_df = lenses_df[lenses_df['규격'] == "FF"]
                    st.caption("ℹ️ 풀프레임(FF) 바디는 FF 전용 렌즈만 신청 가능합니다.")
            
            lens_list = [f"[{row['브랜드']}] {row['모델명']}" for _, row in lenses_df.iterrows()]
            sel_lens_display = st.selectbox("3. 렌즈 선택", ["선택 안 함"] + lens_list)
            sel_lens = sel_lens_display.split("] ", 1)[1] if sel_lens_display != "선택 안 함" else "선택 안 함"

            # 액세서리
            st.write("4. 액세서리 추가")
            a1, a2, a3 = st.columns(3)
            accs = [a for a, c in zip(["SD카드", "리더기", "가방"], [a1.checkbox("SD카드"), a2.checkbox("리더기"), a3.checkbox("가방")]) if c]

            st.markdown('<div class="rental-period-box">', unsafe_allow_html=True)
            name = st.text_input("이름", placeholder="이름을 입력해 주세요")
            contact = st.text_input("연락처", placeholder="010-XXXX-XXXX")
            p1, p2 = st.columns(2)
            start = p1.date_input("대여예정일", min_value=date.today())
            end = p2.date_input("반납예정일", min_value=start, max_value=start + timedelta(days=7))
            
            # 시간 입력란 분리
            t1, t2 = st.columns(2)
            rent_time = t1.text_input("대여 가능 시간 (단위: 시)", placeholder="N~M")
            return_time = t2.text_input("반납 가능 시간 (단위: 시)", placeholder="N~M")
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("신청서 제출하기", use_container_width=True):
                if not name or not contact:
                    st.error("⚠️ 성함과 연락처를 입력해 주세요.")
                elif not rent_time or not return_time:
                    st.error("⚠️ 대여 및 반납 가능 시간을 모두 입력해 주세요.")
                elif sel_mod is None and sel_lens == "선택 안 함":
                    st.error("⚠️ 바디 또는 렌즈 중 최소 하나 이상의 물품을 선택해야 합니다.")
                elif sel_mod and db.check_rental_conflict(sel_mod, start, end):
                    st.error("⚠️ 선택하신 바디가 이미 해당 기간에 예약되어 있습니다.")
                elif sel_lens != "선택 안 함" and db.check_rental_conflict(sel_lens, start, end):
                    st.error("⚠️ 선택하신 렌즈가 이미 해당 기간에 예약되어 있습니다.")
                else:
                    acc_str = ", ".join(accs) if accs else "없음"
                    combined_meet = f"대여: {rent_time} / 반납: {return_time}"
                    new_req = {
                        "신청자": name, "연락처": contact, "장비명": f"[{sel_mod if sel_mod else '바디없음'}] + [{sel_lens}]",
                        "대여시작일": start.strftime("%Y-%m-%d"), "반납예정일": end.strftime("%Y-%m-%d"),
                        "대면시간": combined_meet, "담당자": "미지정", "상태": "대기", "비고": "", "실제반납일": "",
                        "전체이력저장": f"액세서리: {acc_str} | 신청일: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    }
                    if db.submit_rental_request(new_req):
                        st.balloons()
                        st.success("✅ 대여 신청이 성공적으로 완료되었습니다!")
                        st.rerun()

        # 프래그먼트 함수 실행
        render_rental_form(inventory)

# --- 2. 집행부용 관리 ---
elif page == "🛠️ 집행부 전용 관리":
    st.title("🛠️ 집행부 관리 대시보드")
    if "auth" not in st.session_state: st.session_state.auth = False
    if not st.session_state.auth:
        pwd = st.text_input("집행부 비밀번호", type="password", placeholder="비밀번호를 입력해 주세요")
        if st.button("로그인"):
            if pwd == ADMIN_PASSWORD: st.session_state.auth = True; st.rerun()
            else: st.error("비밀번호 오류")
    else:
        if st.sidebar.button("로그아웃"): st.session_state.auth = False; st.rerun()
        tabs = st.tabs(["📌 승인 대기", "✅ 진행 중 대여", "📋 전체 이력", "📷 자산 관리", "⚙️ 설정"])
        rentals = db.get_rentals()

        with tabs[0]: # 승인 대기
            pending = rentals[rentals['상태'] == '대기']
            if pending.empty: st.info("새로운 신청 없음")
            else:
                for idx, row in pending.iterrows():
                    hist = str(row['전체이력저장']); acc_info = hist.split("|")[0].replace("액세서리: ", "") if "액세서리: " in hist else "없음"
                    with st.expander(f"신청: {row['신청자']} - {row['장비명']}"):
                        st.write(f"**기간:** {row['대여시작일']} ~ {row['반납예정일']} | **액세서리:** {acc_info}")
                        c1, c2 = st.columns(2)
                        staff = c1.selectbox("담당자 지정", STAFF_LIST, key=f"s_{idx}")
                        rem = c2.text_input("상세 비고 (집행부용)", key=f"r_{idx}")
                        b1, b2 = st.columns(2)
                        if b1.button("✅ 승인(확정)", key=f"ok_{idx}", use_container_width=True):
                            if db.update_rental_status(row['id'], "확정", staff, rem): st.rerun()
                        if b2.button("❌ 반려(거절)", key=f"no_{idx}", use_container_width=True):
                            if db.update_rental_status(row['id'], "취소", staff, f"[반려] {rem}"): st.rerun()

        with tabs[1]: # 진행 중 (반납 타임스탬프)
            ongoing = rentals[rentals['상태'] == '확정']
            if ongoing.empty: st.info("대여 중인 장비 없음")
            else:
                for idx, row in ongoing.iterrows():
                    with st.expander(f"대여 중: {row['신청자']} (예정: {row['반납예정일']})"):
                        st.write(f"**장비:** {row['장비명']} | **비고:** {row['비고']}")
                        cc1, cc2, cc3 = st.columns(3)
                        new_rem = cc1.text_input("비고 수정", value=row['비고'], key=f"er_{idx}")
                        if cc2.button("🔄 대기 복원", key=f"rv_{idx}", use_container_width=True):
                            if db.update_rental_status(row['id'], "대기", row['담당자'], new_rem): st.rerun()
                        if cc3.button("📦 반납 완료 기록", key=f"dn_{idx}", use_container_width=True):
                            now = datetime.now().strftime("%Y-%m-%d %H:%M")
                            if db.update_rental_status(row['id'], "반납완료", row['담당자'], new_rem, actual_return=now): st.rerun()

        with tabs[2]: st.dataframe(rentals, use_container_width=True)
        with tabs[3]: # 자산 관리
            inv = db.get_inventory(); edit_inv = st.data_editor(inv, num_rows="dynamic", use_container_width=True)
            if st.button("자산 데이터 저장"):
                if db.update_inventory_list(edit_inv): st.success("저장 완료"); st.rerun()

        with tabs[4]:
            st.subheader("⚙️ 비밀번호 관리")
            new_pw = st.text_input("새 비밀번호", value=ADMIN_PASSWORD)
            if st.button("비밀번호 저장"):
                if db.update_settings("admin_password", new_pw): st.success("변경 완료"); st.rerun()

# [END OF APP]
st.markdown("""
    <hr style='border: 0.5px solid #eee; margin: 30px 0 15px 0;'>
    <div style='text-align: center; color: var(--text-color); opacity: 0.6; font-size: 0.8rem; line-height: 1.6;'>
        <b>제작</b> | 45-1기 암실차장 한지원 - Finance&AI융합학부<br>
        <b>위치</b> | 경기도 용인시 처인구 모현읍 외대로 81, 학생회관 414호
    </div>
""", unsafe_allow_html=True)
