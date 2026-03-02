import pandas as pd
import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# ==========================================
# [DB CONFIG] Supabase 연결 및 설정
# ==========================================

@st.cache_resource
def get_supabase_client() -> Client:
    """
    Supabase 클라이언트를 생성하고 캐싱합니다.
    Streamlit secrets에서 정보를 가져오며, 구조적 예외 처리를 포함합니다.
    """
    try:
        # secrets 구조 유연화 (배포 및 로컬 환경 모두 대응)
        if "connections" in st.secrets and "supabase" in st.secrets["connections"]:
            url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
            key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
        elif "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            st.error("❌ Secrets 설정 누락: 'SUPABASE_URL' 정보가 없습니다.")
            return None
            
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Supabase 연결 실패: {e}")
        return None

# ==========================================
# [READ] 데이터 조회 함수 (캐싱 적용)
# ==========================================

@st.cache_data(ttl=300)
def get_inventory() -> pd.DataFrame:
    """
    전체 장비 목록을 조회합니다. (5분 캐싱)
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return pd.DataFrame()
        
        response = supabase.table("Inventory").select("*").execute()
        if not response.data:
            return pd.DataFrame()
            
        df = pd.DataFrame(response.data)
        # 컬럼명 공백 정리
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"❌ 장비 목록 로드 오류: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_rentals() -> pd.DataFrame:
    """
    전체 대여 이력을 최신순으로 조회합니다. (5분 캐싱)
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return pd.DataFrame()
        
        response = supabase.table("Rentals").select("*").order("id", desc=True).execute()
        
        # 필수 컬럼 정의 (데이터가 없을 때를 대비)
        cols = ['id', '신청자', '연락처', '장비명', '대여시작일', '반납예정일', '대면시간', '담당자', '상태', '비고', '실제반납일', '액세서리', '추가요청', '신청일시']
        
        if not response.data:
            return pd.DataFrame(columns=cols)
            
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"❌ 대여 이력 로드 오류: {e}")
        return pd.DataFrame()

def get_settings() -> dict:
    """
    시스템 설정 정보를 딕셔너리 형태로 반환합니다.
    """
    default = {"admin_password": "1111"}
    try:
        supabase = get_supabase_client()
        if not supabase: return default
        
        response = supabase.table("Settings").select("key, value").execute()
        if not response.data: return default
        
        return {item['key']: item['value'] for item in response.data}
    except:
        return default

# ==========================================
# [WRITE] 데이터 변경 함수 (캐시 초기화 포함)
# ==========================================

def submit_rental_request(data: dict) -> bool:
    """
    신청서 데이터를 삽입합니다. 성공 시 True를 반환합니다.
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return False
        
        supabase.table("Rentals").insert(data).execute()
        st.cache_data.clear() # 새 데이터 반영을 위한 캐시 초기화
        return True
    except Exception as e:
        st.error(f"❌ 신청서 제출 실패: {e}")
        return False

def update_rental_status(row_id: int, status: str, staff_name: str, remarks: str = None, actual_return: str = None) -> bool:
    """
    대여 건의 상태와 담당자 정보를 업데이트합니다.
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return False
        
        update_payload = {"상태": status, "담당자": staff_name}
        if remarks is not None: update_payload["비고"] = remarks
        if actual_return is not None: update_payload["실제반납일"] = actual_return
        
        supabase.table("Rentals").update(update_payload).eq("id", row_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ 상태 업데이트 실패: {e}")
        return False

def update_settings(key: str, value: str) -> bool:
    """
    특정 설정 값을 업데이트합니다.
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return False
        
        supabase.table("Settings").update({"value": value}).eq("key", key).execute()
        st.cache_data.clear()
        return True
    except:
        return False

def check_rental_conflict(equipment_name: str, start_date, end_date) -> bool:
    """
    지정된 기간 내 특정 장비의 예약 중복 여부를 확인합니다.
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return False
        
        # 최적화: 필요한 조건으로 DB에서 미리 필터링
        res = supabase.table("Rentals") \
            .select("대여시작일, 반납예정일") \
            .ilike("장비명", f"%{equipment_name}%") \
            .in_("상태", ["확정", "대여중", "대기"]) \
            .execute()
        
        if not res.data: return False
        
        for row in res.data:
            s = pd.to_datetime(row['대여시작일']).date()
            e = pd.to_datetime(row['반납예정일']).date()
            if (start_date <= e) and (end_date >= s):
                return True
        return False
    except:
        return False

def update_inventory_list(df: pd.DataFrame) -> bool:
    """
    자산 목록을 일괄 업데이트(Upsert)합니다.
    """
    try:
        supabase = get_supabase_client()
        if not supabase: return False
        
        # 데이터 정제 (NaN -> None 처리로 DB 오류 방지)
        clean_data = df.replace({pd.NA: None, float('nan'): None}).to_dict(orient='records')
        if clean_data:
            supabase.table("Inventory").upsert(clean_data).execute()
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ 자산 업데이트 실패: {e}")
        return False
