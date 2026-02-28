import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
from datetime import datetime

def get_gspread_client():
    """구글 시트 API 인증"""
    try:
        creds_dict = st.secrets["connections"]["gsheets"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        private_key = creds_dict["private_key"].replace("\\n", "\n")
        info = {
            "type": creds_dict["type"], "project_id": creds_dict["project_id"],
            "private_key_id": creds_dict["private_key_id"], "private_key": private_key,
            "client_email": creds_dict["client_email"], "client_id": creds_dict["client_id"],
            "auth_uri": creds_dict["auth_uri"], "token_uri": creds_dict["token_uri"],
            "auth_provider_x509_cert_url": creds_dict["auth_provider_x509_cert_url"],
            "client_x509_cert_url": creds_dict["client_x509_cert_url"]
        }
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ 구글 인증 실패: {e}")
        return None

@st.cache_data(ttl=300)
def get_data_from_sheet(worksheet_name):
    """캐싱 적용 데이터 로드 (헤더 강제 매핑 및 줄바꿈 정리)"""
    try:
        client = get_gspread_client()
        if client is None: return pd.DataFrame()
        
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = client.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet(worksheet_name)
        
        raw_data = worksheet.get_all_values()
        if not raw_data or len(raw_data) < 2: # 최소 헤더 + 데이터 1줄 필요
            return pd.DataFrame()
        
        # 첫 줄(헤더) 정리: 줄바꿈 제거 및 공백 제거
        header = [str(h).strip().replace("\n", "").replace(" ", "") for h in raw_data[0]]
        
        # [CRITICAL] 6번째 컬럼이 비어있으면 '상태'로 강제 지정 (시트 수정 누락 방지)
        if worksheet_name == "Inventory" and len(header) >= 6 and not header[5]:
            header[5] = "상태"
        
        df = pd.DataFrame(raw_data[1:], columns=header)
        
        # 모든 행이 비어있는 경우 제거 (데이터가 없는 행이 딸려올 수 있음)
        df = df.replace("", None).dropna(how='all')
        
        return df
    except Exception as e:
        st.error(f"❌ '{worksheet_name}' 로드 실패: {e}")
        return pd.DataFrame()

def get_inventory():
    """장비 목록 로드 (구분, 카테고리, 브랜드, 모델명, 규격, 상태)"""
    df = get_data_from_sheet("Inventory")
    if not df.empty: df.columns = [c.strip() for c in df.columns]
    return df

def get_rentals():
    """대여 이력 로드"""
    df = get_data_from_sheet("Rentals")
    return df if not df.empty else pd.DataFrame(columns=['신청자', '연락처', '장비명', '대여시작일', '반납예정일', '대면시간', '담당자', '상태', '비고', '실제반납일', '전체이력저장'])

def get_settings():
    """설정 정보 로드"""
    df = get_data_from_sheet("Settings")
    default = {"admin_password": "nuriye_admin"}
    if df.empty: return default
    df.columns = [str(c).strip().capitalize() for c in df.columns]
    if 'Key' in df.columns and 'Value' in df.columns:
        return dict(zip(df['Key'].astype(str), df['Value'].astype(str)))
    return default

def update_settings(key, value):
    try:
        client = get_gspread_client()
        sh = client.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        worksheet = sh.worksheet("Settings")
        cell = worksheet.find(key)
        if cell: worksheet.update_cell(cell.row, cell.col + 1, value)
        st.cache_data.clear()
        return True
    except: return False

def submit_rental_request(data):
    """신청서 데이터 전송"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        worksheet = sh.worksheet("Rentals")
        header = ['신청자', '연락처', '장비명', '대여시작일', '반납예정일', '대면시간', '담당자', '상태', '비고', '실제반납일', '전체이력저장']
        worksheet.append_row([data.get(h, "") for h in header])
        st.cache_data.clear()
        return True
    except: return False

def update_rental_status(row_index, status, staff_name, remarks=None, actual_return=None):
    """상태 변경 및 반납 시간 자동 기록"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        worksheet = sh.worksheet("Rentals")
        row = row_index + 2
        worksheet.update_cell(row, 8, status)
        worksheet.update_cell(row, 7, staff_name)
        if remarks is not None: worksheet.update_cell(row, 9, remarks)
        if actual_return is not None: worksheet.update_cell(row, 10, actual_return)
        st.cache_data.clear()
        return True
    except: return False

def check_rental_conflict(equipment_name, start_date, end_date):
    """예약 중복 체크"""
    rentals = get_rentals()
    if rentals.empty: return False
    active = rentals[(rentals['장비명'].astype(str).str.contains(str(equipment_name), na=False)) & 
                     (rentals['상태'].astype(str).str.strip().isin(['대기', '확정', '대여중']))]
    for _, row in active.iterrows():
        try:
            s = pd.to_datetime(str(row['대여시작일'])).date()
            e = pd.to_datetime(str(row['반납예정일'])).date()
            if (start_date <= e) and (end_date >= s): return True
        except: continue
    return False

def update_inventory_list(df):
    """재고 시트 업데이트"""
    try:
        client = get_gspread_client()
        sh = client.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        worksheet = sh.worksheet("Inventory")
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear()
        return True
    except: return False
