import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import database as db

# ==========================================
# [1] 앱 기본 설정 및 테마 시스템
# ==========================================

st.set_page_config(
    page_title="누리예 카메라 대여 시스템", 
    page_icon="📸", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

def inject_custom_styles(theme_mode):
    # """테마 선택에 따라 동적 CSS를 주입하는 함수"""
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

    def make_vars(base):
        return f"""
            --bg-color: {base['bg']}; --text-color: {base['text']}; --container-bg: {base['cont']};
            --input-bg: {base['input']}; --border-color: {base['brd']}; --calendar-header-bg: {base['cal_h']};
            --calendar-day-bg: {base['cal_d']}; --calendar-empty-bg: {base['cal_e']};
            --main-brand-color: {base['brand']}; --button-text: {base['btn_t']};
        """

    dark_extra = ".rental-line { border: 1px solid rgba(255,255,255,0.2); filter: saturate(1.2) brightness(1.1); } .calendar-day.empty { background-color: var(--calendar-empty-bg) !important; }"

    if theme_mode == "시스템 설정":
        dynamic_css = f":root {{ {make_vars(THEMES['light'])} }} @media (prefers-color-scheme: dark) {{ :root {{ {make_vars(THEMES['dark'])} }} {dark_extra} }}"
    elif theme_mode == "라이트":
        dynamic_css = f":root {{ {make_vars(THEMES['light'])} }}"
    else:
        dynamic_css = f":root {{ {make_vars(THEMES['dark'])} }} {dark_extra}"

    try:
        with open('style.css', encoding='utf-8') as f:
            st.markdown(f"<style>{f.read()}{dynamic_css}</style>", unsafe_allow_html=True)
    except: pass

# 사이드바 테마 토글
theme_choice = st.sidebar.selectbox("테마 선택", ["시스템 설정", "라이트", "다크"], index=0)
inject_custom_styles(theme_choice)

# ==========================================
# [2] 유틸리티 및 데이터 로드
# ==========================================

# 설정 데이터 로드
settings = db.get_settings()
ADMIN_PASSWORD = settings.get("admin_password", "1111")
STAFF_LIST = ["[암실부장] 김지원", "[회장] 유재동", "[부회장] 한지원", "[총무] 심종율", "[홍보부장] 이서윤", "[홍보차장] 김예은", "[홍보차장] 김기연"]

def get_calendar_html(rentals, view_year, view_month, is_admin=False):
    """대여 현황 캘린더 HTML 생성 (성능 최적화 버전)"""
    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(view_year, view_month)
    today = date.today()
    
    # [OPTIMIZATION] 루프 외부에서 이번 달에 해당하는 '확정/대여중' 데이터만 미리 필터링
    # 캘린더 셀마다 수십 개의 데이터를 반복 검사하는 비용을 대폭 줄임
    active_rentals = rentals[rentals['상태'].isin(['확정', '대여중'])].copy()
    if not active_rentals.empty:
        active_rentals['start_dt'] = pd.to_datetime(active_rentals['대여시작일']).dt.date
        active_rentals['end_dt'] = pd.to_datetime(active_rentals['반납예정일']).dt.date

    # 캘린더 기본 구조
    html = '<div class="calendar-container"><div class="calendar-grid">'
    for d in ["일", "월", "화", "수", "목", "금", "토"]:
        html += f'<div class="calendar-header">{d}</div>'
    
    colors = ["#FF5252", "#448AFF", "#4CAF50", "#FFC107", "#9C27B0", "#00BCD4", "#E91E63"]
    
    for week in cal:
        for day in week:
            if day == 0:
                html += '<div class="calendar-day empty"></div>'
                continue
                
            day_date = date(view_year, view_month, day)
            is_today = "today" if day_date == today else ""
            html += f'<div class="calendar-day {is_today}"><b>{day}</b>'
            
            # 해당 날짜에 겹치는 대여 건 추출
            day_matches = []
            if not active_rentals.empty:
                matches = active_rentals[(active_rentals['start_dt'] <= day_date) & (active_rentals['end_dt'] >= day_date)]
                day_matches = matches.to_dict('records')
            
            for i, r in enumerate(day_matches[:3]):
                color = colors[i % len(colors)]
                acc = r.get('액세서리', '없음')
                rem_info = f" | 비고: {r['비고']}" if is_admin and r.get('비고') else ""
                tooltip = f"{r['신청자']} / {r['장비명']} / 액세서리: {acc}{rem_info}"
                html += f'<div class="rental-line" style="background: {color};" data-tooltip="{tooltip}"></div>'
            
            if len(day_matches) > 3:
                html += f'<div style="font-size: 0.6rem; font-weight: bold;">+ {len(day_matches)-3}건</div>'
            html += '</div>'
            
    html += '</div></div>'
    return html

# ==========================================
# [3] 내비게이션 및 페이지 레이아웃
# ==========================================

page = st.sidebar.selectbox("메뉴 선택", ["📸 대여 신청 및 현황", "🛠️ 집행부 전용 관리"], key="nav")
if st.sidebar.button("데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

# --- 1. 부원용 신청/현황 페이지 ---
if page == "📸 대여 신청 및 현황":
    st.title("📸 누리예 카메라 대여 시스템")
    
    # 캘린더 날짜 제어 (세션 상태 활용)
    if 'vy' not in st.session_state: st.session_state.vy = date.today().year
    if 'vm' not in st.session_state: st.session_state.vm = date.today().month

    inventory = db.get_inventory()
    rentals = db.get_rentals()

    col_l, col_r = st.columns([7, 5], gap="large")

    # [좌측] 대여 현황 캘린더 구역
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
        
        st.markdown(get_calendar_html(rentals, st.session_state.vy, st.session_state.vm), unsafe_allow_html=True)

    # [우측] 스마트 대여 신청 양식 구역
    with col_r:
        st.subheader("카메라/렌즈 대여 신청")
        
        @st.fragment
        def render_rental_form(inv):
            """신청 양식 조각 (Fragment) - 위젯 조작 시 페이지 전체 리런 방지"""
            if inv.empty:
                st.warning("현재 대여 가능한 장비 목록을 불러올 수 없습니다.")
                return

            # (1) 카테고리 및 모델 선택
            raw_cats = inv[inv['구분'] == 'Body']['카테고리'].unique().tolist()
            clean_cats = sorted(list(set([c.replace("DSLR(크롭)", "DSLR (크롭)") for c in raw_cats])))
            sel_cat = st.selectbox("1. 카메라 카테고리", ["선택 안 함"] + clean_cats)
            
            mods_df = inv[(inv['구분'] == 'Body') & (inv['카테고리'] == sel_cat)]
            mod_display_list = [f"[{row['브랜드']}] {row['모델명']}" for _, row in mods_df.iterrows()]
            sel_mod_disp = st.selectbox("2. 카메라 모델", mod_display_list, index=None, placeholder="바디 미선택 시 렌즈만 대여 가능")
            sel_mod = sel_mod_disp.split("] ", 1)[1] if sel_mod_disp else None
            
            # (2) 렌즈 호환성 필터링
            lenses_df = inv[(inv['구분'] == 'Lens') & (inv['상태'] == '대여가능')]
            if sel_mod:
                b_info = mods_df[mods_df['모델명'] == sel_mod].iloc[0]
                compat_brands = [str(b_info['브랜드']).strip()]
                if compat_brands[0] == "Canon": compat_brands.append("Tamron")
                lenses_df = lenses_df[lenses_df['브랜드'].isin(compat_brands)]
                if str(b_info['규격']).strip() == "FF":
                    lenses_df = lenses_df[lenses_df['규격'] == "FF"]
                    st.caption("풀프레임(FF) 바디는 FF 전용 렌즈만 신청 가능합니다.")
            
            lens_list = [f"[{row['브랜드']}] {row['모델명']}" for _, row in lenses_df.iterrows()]
            sel_lens_disp = st.selectbox("3. 렌즈 모델", ["선택 안 함"] + lens_list)
            sel_lens = sel_lens_disp.split("] ", 1)[1] if sel_lens_disp != "선택 안 함" else "선택 안 함"

            # (3) 액세서리 및 요청사항
            st.write("엑세서리 추가 (선택)")
            acc_cols = st.columns(4)
            acc_items = ["카메라 충전기", "SD카드 리더기", "카메라 가방", "삼각대"]
            accs = [item for i, item in enumerate(acc_items) if acc_cols[i].checkbox(item)]
            extra_req = st.text_input("추가 요청사항 (선택)", placeholder="추가 요청사항을 입력해주세요")

            # (4) 예약 상세 (날짜 및 시간)
            st.markdown('<div class="rental-period-box">', unsafe_allow_html=True)
            u_name = st.text_input("이름", placeholder="이름을 입력해 주세요")
            u_contact = st.text_input("연락처", placeholder="010-XXXX-XXXX")
            p1, p2 = st.columns(2)
            start_d = p1.date_input("대여예정일", min_value=date.today())
            end_d = p2.date_input("반납예정일", min_value=start_d, max_value=start_d + timedelta(days=7))
            t1, t2 = st.columns(2)
            time_r = t1.text_input("대여 가능 시간 (단위: 시)", placeholder="N~M")
            time_b = t2.text_input("반납 가능 시간 (단위: 시)", placeholder="N~M")
            st.markdown('</div>', unsafe_allow_html=True)

            # (5) 제출 로직 및 무결성 검사
            if st.button("신청서 제출하기", use_container_width=True):
                if not u_name or not u_contact:
                    st.error("⚠️ 성함과 연락처를 입력해 주세요.")
                elif not time_r or not time_b:
                    st.error("⚠️ 대여 및 반납 가능 시간을 모두 입력해 주세요.")
                elif sel_mod is None and sel_lens == "선택 안 함":
                    st.error("⚠️ 바디 또는 렌즈 중 최소 하나 이상의 물품을 선택해야 합니다.")
                elif sel_mod and db.check_rental_conflict(sel_mod, start_d, end_d):
                    st.error(f"⚠️ 선택하신 바디({sel_mod})는 해당 기간에 예약이 불가능합니다.")
                elif sel_lens != "선택 안 함" and db.check_rental_conflict(sel_lens, start_d, end_d):
                    st.error(f"⚠️ 선택하신 렌즈({sel_lens})는 해당 기간에 예약이 불가능합니다.")
                else:
                    new_data = {
                        "신청자": u_name, "연락처": u_contact, "장비명": f"[{sel_mod if sel_mod else '바디없음'}] + [{sel_lens}]",
                        "대여시작일": start_d.strftime("%Y-%m-%d"), "반납예정일": end_d.strftime("%Y-%m-%d"),
                        "대면시간": f"대여: {time_r} / 반납: {time_b}", "담당자": "미지정", "상태": "대기", 
                        "비고": "", "실제반납일": "", "액세서리": ", ".join(accs) if accs else "없음",
                        "추가요청": extra_req if extra_req.strip() else "없음", "신청일시": datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
                    if db.submit_rental_request(new_data):
                        st.balloons()
                        st.success("✅ 대여 신청이 성공적으로 완료되었습니다!")
                        st.rerun()

        render_rental_form(inventory)

# --- 2. 집행부용 관리 페이지 ---
elif page == "🛠️ 집행부 전용 관리":
    st.title("🛠️ 집행부 관리 대시보드")
    
    if "auth" not in st.session_state: st.session_state.auth = False
    
    if not st.session_state.auth:
        pwd = st.text_input("집행부 비밀번호", type="password", placeholder="비밀번호를 입력해 주세요")
        if st.button("로그인"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else: st.error("비밀번호가 올바르지 않습니다.")
    else:
        if st.sidebar.button("로그아웃"): 
            st.session_state.auth = False
            st.rerun()
            
        tabs = st.tabs(["승인 대기", "진행 중 대여", "전체 이력", "장비 목록", "설정"])
        rentals = db.get_rentals()

        with tabs[0]: # [승인 대기]
            pending = rentals[rentals['상태'] == '대기']
            if pending.empty: st.info("새로운 대여 신청이 없습니다.")
            else:
                for idx, row in pending.iterrows():
                    with st.expander(f"신청: {row['신청자']} - {row['장비명']}"):
                        st.write(f"**기간:** {row['대여시작일']} ~ {row['반납예정일']}")
                        st.write(f"**액세서리:** {row['액세서리']} | **요청사항:** {row['추가요청']}")
                        st.write(f"**신청일시:** {row['신청일시']}")
                        c1, c2 = st.columns(2)
                        staff = c1.selectbox("담당자 지정", STAFF_LIST, key=f"s_{idx}")
                        rem = c2.text_input("상세 비고 (집행부용)", key=f"r_{idx}")
                        b1, b2 = st.columns(2)
                        if b1.button("✅ 승인(확정)", key=f"ok_{idx}", use_container_width=True):
                            if db.update_rental_status(row['id'], "확정", staff, rem): st.rerun()
                        if b2.button("❌ 반려(거절)", key=f"no_{idx}", use_container_width=True):
                            if db.update_rental_status(row['id'], "취소", staff, f"[반려] {rem}"): st.rerun()

        with tabs[1]: # [진행 중 대여]
            ongoing = rentals[rentals['상태'] == '확정']
            if ongoing.empty: st.info("현재 대여 중인 장비가 없습니다.")
            else:
                today_dt = date.today()
                for idx, row in ongoing.iterrows():
                    # D-Day 계산 로직
                    target = pd.to_datetime(row['반납예정일']).date()
                    diff = (target - today_dt).days
                    d_day = f"D-{diff}" if diff > 0 else ("D-day" if diff == 0 else f"D+{abs(diff)}")
                    d_color = "#FF5252" if diff <= 1 else "var(--text-color)"
                    
                    title = f"{row['신청자']} | {row['장비명']} | {row['대여시작일']} ~ {row['반납예정일']} ({d_day})"
                    with st.expander(title):
                        st.write(f"**상세 장비:** {row['장비명']}")
                        st.write(f"**액세서리:** {row['액세서리']}")
                        st.write(f"**비고:** {row['비고']}")
                        cc1, cc2, cc3 = st.columns(3)
                        n_rem = cc1.text_input("비고 수정", value=row['비고'], key=f"er_{idx}")
                        if cc2.button("대기 복원", key=f"rv_{idx}", use_container_width=True):
                            if db.update_rental_status(row['id'], "대기", row['담당자'], n_rem): st.rerun()
                        if cc3.button("반납 완료", key=f"dn_{idx}", use_container_width=True):
                            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                            if db.update_rental_status(row['id'], "반납완료", row['담당자'], n_rem, actual_return=now_ts): st.rerun()

        with tabs[2]: st.dataframe(rentals, use_container_width=True)
        with tabs[3]: # [자산 관리]
            inv_data = db.get_inventory()
            edited_inv = st.data_editor(inv_data, num_rows="dynamic", use_container_width=True)
            if st.button("자산 데이터 저장"):
                if db.update_inventory_list(edited_inv):
                    st.success("자산 정보가 성공적으로 업데이트되었습니다.")
                    st.rerun()

        with tabs[4]: # [설정]
            st.subheader("시스템 설정")
            new_pwd = st.text_input("새 관리자 비밀번호", value=ADMIN_PASSWORD)
            if st.button("비밀번호 변경 저장"):
                if db.update_settings("admin_password", new_pwd):
                    st.success("비밀번호가 변경되었습니다.")
                    st.rerun()

# ==========================================
# [4] 앱 하단 정보 (Footer)
# ==========================================

st.markdown("""
    <hr style='border: 0.5px solid #eee; margin: 30px 0 15px 0;'>
    <div style='text-align: center; color: var(--text-color); opacity: 0.6; font-size: 0.8rem; line-height: 1.6;'>
        <b>제작</b> | 45-1기 암실차장 한지원 - Finance&AI융합학부<br>
        <b>위치</b> | 경기도 용인시 처인구 모현읍 외대로 81, 학생회관 414호
    </div>
""", unsafe_allow_html=True)
