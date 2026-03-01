import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# [CONFIG] Supabase 연결 설정
@st.cache_resource
def get_supabase_client() -> Client:
    try:
        url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
        key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Supabase 연결 실패: {e}")
        return None

@st.cache_data(ttl=300)
def get_inventory():
    """장비 목록 로드 (Inventory 테이블)"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("Inventory").select("*").execute()
        
        # 상세 진단 로그
        if not response.data:
            st.warning("⚠️ Supabase 'Inventory' 테이블에 데이터가 비어있거나 정책(RLS)에 의해 차단되었습니다.")
            return pd.DataFrame()
            
        df = pd.DataFrame(response.data)
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"❌ 장비 목록 로드 중 치명적 오류: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_rentals():
    """대여 이력 로드 (Rentals 테이블)"""
    try:
        supabase = get_supabase_client()
        # id 내림차순 정렬 (최신순)
        response = supabase.table("Rentals").select("*").order("id", desc=True).execute()
        
        if not response.data:
            st.info("ℹ️ 대여 이력이 없거나 접근 권한(RLS)이 없습니다.")
            return pd.DataFrame(columns=['id', '신청자', '연락처', '장비명', '대여시작일', '반납예정일', '대면시간', '담당자', '상태', '비고', '실제반납일', '전체이력저장'])
            
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        st.error(f"❌ 대여 이력 로드 중 치명적 오류: {e}")
        return pd.DataFrame(columns=['id', '신청자', '연락처', '장비명', '대여시작일', '반납예정일', '대면시간', '담당자', '상태', '비고', '실제반납일', '전체이력저장'])

def get_settings():
    """설정 정보 로드 (Settings 테이블)"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("Settings").select("*").execute()
        data = response.data
        default = {"admin_password": "1111"}
        if not data: return default
        
        # {key: value} 딕셔너리로 변환
        settings_dict = {item['key']: item['value'] for item in data}
        return settings_dict
    except:
        return {"admin_password": "1111"}

def update_settings(key, value):
    """설정 정보 업데이트"""
    try:
        supabase = get_supabase_client()
        supabase.table("Settings").update({"value": value}).eq("key", key).execute()
        st.cache_data.clear()
        return True
    except:
        return False

def submit_rental_request(data):
    """신청서 데이터 전송 (INSERT)"""
    try:
        supabase = get_supabase_client()
        # 딕셔너리 데이터를 그대로 Insert
        supabase.table("Rentals").insert(data).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ 신청서 제출 실패: {e}")
        return False

def update_rental_status(row_id, status, staff_name, remarks=None, actual_return=None):
    """대여 상태 업데이트 (UPDATE)"""
    try:
        supabase = get_supabase_client()
        update_data = {
            "상태": status,
            "담당자": staff_name
        }
        if remarks is not None: update_data["비고"] = remarks
        if actual_return is not None: update_data["실제반납일"] = actual_return
        
        # 시트 인덱스 대신 실제 id(PK)를 사용하여 업데이트
        supabase.table("Rentals").update(update_data).eq("id", row_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ 상태 업데이트 실패: {e}")
        return False

def check_rental_conflict(equipment_name, start_date, end_date):
    """예약 중복 체크 (DB 쿼리 활용)"""
    try:
        supabase = get_supabase_client()
        # 해당 장비를 포함하고 활성화된 예약만 필터링
        response = supabase.table("Rentals") \
            .select("*") \
            .ilike("장비명", f"%{equipment_name}%") \
            .in_("상태", ["대기", "확정", "대여중"]) \
            .execute()
        
        active_rentals = pd.DataFrame(response.data)
        if active_rentals.empty: return False
        
        for _, row in active_rentals.iterrows():
            try:
                s = pd.to_datetime(str(row['대여시작일'])).date()
                e = pd.to_datetime(str(row['반납예정일'])).date()
                if (start_date <= e) and (end_date >= s): return True
            except: continue
        return False
    except:
        return False

def update_inventory_list(df):
    """재고 목록 전체 업데이트 (주의: 전체 삭제 후 재삽입)"""
    try:
        supabase = get_supabase_client()
        # 기존 데이터 삭제 (PostgreSQL 정책에 따라 다를 수 있음)
        # 여기서는 단순히 데이터프레임의 각 행을 upsert 하는 방식으로 처리 제안
        data_list = df.to_dict(orient='records')
        for item in data_list:
            supabase.table("Inventory").upsert(item).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ 자산 업데이트 실패: {e}")
        return False
