import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import gsheets as gs

# [PWA/Base Settings] 앱 설정
st.set_page_config(page_title="누리예 카메라 대여 시스템", page_icon="📸", layout="wide", initial_sidebar_state="collapsed")

# [STYLE] CSS 로드 및 테마 전환 로직
theme_mode = st.sidebar.selectbox("🌓 테마 선택", ["시스템 설정", "라이트", "다크"], index=0)

# 테마별 색상 변수 정의
light_vars = """
    --bg-color: #FFFFFF; --text-color: #000000; --container-bg: #FFFFFF;
    --input-bg: #FFFFFF; --border-color: #cccccc; --calendar-header-bg: #fdfdfd;
    --calendar-day-bg: #FFFFFF; --calendar-empty-bg: #fdfdfd;
    --main-brand-color: #B2DFDB; --button-text: #FFFFFF; /* 라이트모드 버튼 글자색: 흰색 */
"""
dark_vars = """
    --bg-color: #121212; --text-color: #E0E0E0; --container-bg: #1E1E1E;
    --input-bg: #252525; --border-color: #333333; --calendar-header-bg: #252525;
    --calendar-day-bg: #1E1E1E; --calendar-empty-bg: #181818;
    --main-brand-color: #5a9490; --button-text: #000000; /* 다크모드 버튼 글자색: 검정색 */
"""
dark_extra_css = ".rental-line { border: 1px solid rgba(255,255,255,0.2); filter: saturate(1.2) brightness(1.1); } .calendar-day.empty { background-color: var(--calendar-empty-bg) !important; }"

# 선택에 따른 동적 CSS 생성
if theme_mode == "시스템 설정":
    dynamic_css = f":root {{ {light_vars} }} @media (prefers-color-scheme: dark) {{ :root {{ {dark_vars} }} {dark_extra_css} }}"
elif theme_mode == "라이트":
    dynamic_css = f":root {{ {light_vars} }}"
else: # 다크
    dynamic_css = f":root {{ {dark_vars} }} {dark_extra_css}"

try:
    with open('style.css', encoding='utf-8') as f:
        css_content = f.read()
        st.markdown(f"<style>{css_content}{dynamic_css}</style>", unsafe_allow_html=True)
except Exception: pass

# 설정 및 데이터 로드
settings = gs.get_settings()
ADMIN_PASSWORD = settings.get("admin_password", "nuriye1234")
STAFF_LIST = ["유재동(회장)", "한지원(부회장)", "김지원(암실부장)", "심종율(총무)", "이서운(홍보부장)", "김기연(홍보차장)", "김예은(홍보차장)"]

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
if st.sidebar.button("🔄 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

# --- 1. 부원용 신청/현황 ---
if page == "📸 대여 신청 및 현황":
    st.title("📸 누리예 카메라 대여 시스템")
    if 'vy' not in st.session_state: st.session_state.vy = date.today().year
    if 'vm' not in st.session_state: st.session_state.vm = date.today().month

    inventory = gs.get_inventory()
    rentals = gs.get_rentals()

    col_l, col_r = st.columns([7, 5], gap="large")

    with col_l:
        n1, n2, n3 = st.columns([1, 5, 1])
        with n1:
            if st.button("◀", key="p_m"):
                if st.session_state.vm == 1: st.session_state.vm = 12; st.session_state.vy -= 1
                else: st.session_state.vm -= 1
                st.rerun()
        with n2: st.markdown(f"<h3 style='text-align: center;'>🗓️ {st.session_state.vy}년 {st.session_state.vm}월 대여 현황</h3>", unsafe_allow_html=True)
        with n3:
            if st.button("▶", key="n_m"):
                if st.session_state.vm == 12: st.session_state.vm = 1; st.session_state.vy += 1
                else: st.session_state.vm += 1
                st.rerun()
        st.markdown(get_calendar_html(rentals, st.session_state.vy, st.session_state.vm, is_admin=False), unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="form-container">', unsafe_allow_html=True)
        st.subheader("📷 스마트 대여 신청")
        if inventory.empty: st.error("장비 정보를 불러올 수 없습니다.")
        else:
            # 바디 선택 (Category -> Model)
            b_cats = ["선택하세요"] + inventory[inventory['구분'] == 'Body']['카테고리'].unique().tolist()
            sel_cat = st.selectbox("1. 바디 카테고리 (필요 시)", b_cats)
            
            mods_df = inventory[(inventory['구분'] == 'Body') & (inventory['카테고리'] == sel_cat)]
            sel_mod = st.selectbox("2. 카메라 바디 모델", mods_df['모델명'].unique().tolist() if not mods_df.empty else [], index=None, placeholder="바디 미선택 시 렌즈만 대여 가능")
            
            # [VS Code 로직] 유연한 렌즈 필터링
            lenses_df = inventory[(inventory['구분'] == 'Lens') & (inventory['상태'] == '대여가능')]
            
            if sel_mod:
                b_info = mods_df[mods_df['모델명'] == sel_mod].iloc[0]
                b_brand = str(b_info['브랜드']).strip()
                b_spec = str(b_info['규격']).strip() # FF or Crop

                # 브랜드 호환성 (Canon-Tamron 예외)
                compat_brands = [b_brand]
                if b_brand == "Canon": compat_brands.append("Tamron")
                lenses_df = lenses_df[lenses_df['브랜드'].isin(compat_brands)]
                
                # 센서 호환성 (FF바디는 FF렌즈만)
                if b_spec == "FF":
                    lenses_df = lenses_df[lenses_df['규격'] == "FF"]
                    st.caption("ℹ️ 풀프레임(FF) 바디는 FF 전용 렌즈만 신청 가능합니다.")
            
            lens_list = [f"[{row['브랜드']}] {row['모델명']}" for _, row in lenses_df.iterrows()]
            sel_lens_display = st.selectbox("3. 호환 렌즈 선택 (필요 시)", ["선택안함"] + lens_list)
            sel_lens = sel_lens_display.split("] ", 1)[1] if sel_lens_display != "선택안함" else "선택안함"

            # 액세서리
            st.write("4. 액세서리 추가")
            a1, a2, a3 = st.columns(3)
            accs = [a for a, c in zip(["SD카드", "리더기", "가방"], [a1.checkbox("SD카드"), a2.checkbox("리더기"), a3.checkbox("가방")]) if c]

            st.markdown('<div class="rental-period-box">', unsafe_allow_html=True)
            name = st.text_input("신청자 성함", placeholder="실명을 입력해 주세요")
            contact = st.text_input("연락처", placeholder="010-XXXX-XXXX")
            p1, p2 = st.columns(2)
            start = p1.date_input("대여예정일", min_value=date.today())
            end = p2.date_input("반납예정일", min_value=start, max_value=start + timedelta(days=7))
            meet = st.text_input("대여/반납 가능 시간", placeholder="대여: N~M시 / 반납: N~M시")
            st.markdown('</div>', unsafe_allow_html=True)

            # [VALIDATION] 신청서 제출 검증 로직
            submit_ready = False
            if st.button("신청서 제출하기", use_container_width=True):
                if not name or not contact:
                    st.error("⚠️ 성함과 연락처를 입력해 주세요.")
                elif sel_mod is None and sel_lens == "선택안함":
                    st.error("⚠️ 바디 또는 렌즈 중 최소 하나 이상의 물품을 선택해야 합니다.")
                elif sel_mod and gs.check_rental_conflict(sel_mod, start, end):
                    st.error("⚠️ 선택하신 바디가 이미 해당 기간에 예약되어 있습니다.")
                elif sel_lens != "선택안함" and gs.check_rental_conflict(sel_lens, start, end):
                    st.error("⚠️ 선택하신 렌즈가 이미 해당 기간에 예약되어 있습니다.")
                else:
                    acc_str = ", ".join(accs) if accs else "없음"
                    new_req = {
                        "신청자": name, "연락처": contact, "장비명": f"[{sel_mod if sel_mod else '바디없음'}] + [{sel_lens}]",
                        "대여시작일": start.strftime("%Y-%m-%d"), "반납예정일": end.strftime("%Y-%m-%d"),
                        "대면시간": meet, "담당자": "미지정", "상태": "대기", "비고": "", "실제반납일": "",
                        "전체이력저장": f"액세서리: {acc_str} | 신청일: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    }
                    if gs.submit_rental_request(new_req):
                        st.balloons()
                        st.success("✅ 대여 신청이 성공적으로 완료되었습니다!")
                        st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 2. 집행부용 관리 ---
elif page == "🛠️ 집행부 전용 관리":
    st.title("🛠️ 집행부 관리 대시보드")
    if "auth" not in st.session_state: st.session_state.auth = False
    if not st.session_state.auth:
        pwd = st.text_input("집행부 인증번호(PW)", type="password")
        if st.button("로그인"):
            if pwd == ADMIN_PASSWORD: st.session_state.auth = True; st.rerun()
            else: st.error("비밀번호 오류")
    else:
        if st.sidebar.button("로그아웃"): st.session_state.auth = False; st.rerun()
        tabs = st.tabs(["📌 승인 대기", "✅ 진행 중 대여", "📋 전체 이력", "📷 자산 관리", "⚙️ 설정"])
        rentals = gs.get_rentals()

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
                            if gs.update_rental_status(idx, "확정", staff, rem): st.rerun()
                        if b2.button("❌ 반려(거절)", key=f"no_{idx}", use_container_width=True):
                            if gs.update_rental_status(idx, "취소", staff, f"[반려] {rem}"): st.rerun()

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
                            if gs.update_rental_status(idx, "대기", row['담당자'], new_rem): st.rerun()
                        if cc3.button("📦 반납 완료 기록", key=f"dn_{idx}", use_container_width=True):
                            now = datetime.now().strftime("%Y-%m-%d %H:%M")
                            if gs.update_rental_status(idx, "반납완료", row['담당자'], new_rem, actual_return=now): st.rerun()

        with tabs[2]: st.dataframe(rentals, use_container_width=True)
        with tabs[3]: # 자산 관리
            inv = gs.get_inventory(); edit_inv = st.data_editor(inv, num_rows="dynamic", use_container_width=True)
            if st.button("자산 데이터 저장"):
                if gs.update_inventory_list(edit_inv): st.success("저장 완료"); st.rerun()

        with tabs[4]:
            st.subheader("⚙️ 비밀번호 관리")
            new_pw = st.text_input("새 비밀번호", value=ADMIN_PASSWORD)
            if st.button("비밀번호 저장"):
                if gs.update_settings("admin_password", new_pw): st.success("변경 완료"); st.rerun()

# [END OF APP]
st.markdown("""
    <hr style='border: 0.5px solid #eee; margin: 30px 0 15px 0;'>
    <div style='text-align: center; color: var(--text-color); opacity: 0.6; font-size: 0.8rem; line-height: 1.6;'>
        <b>제작</b> | 45-1기 암실차장 한지원 - Finance&AI융합학부<br>
        <b>동아리방</b> | 경기도 용인시 처인구 모현읍 외대로 81, 학생회관 414호
    </div>
""", unsafe_allow_html=True)
