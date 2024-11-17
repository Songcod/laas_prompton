# python api_googlesheet.py로 실행

from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import pandas as pd

app = Flask(__name__)

DEFAULT_SHEET_ID = '1-FrSfYWgFkLvZ-AfqggY0-sXhZbATbGaCWXYhzPPf5Q'
SERVICE_ACCOUNT_PATH = 'db3clothbtitest-b2ab2e525277.json'

def read_google_sheet(sheet_id, service_account_path, sheet_name):
    """
    Google Sheets 데이터를 읽고 빈 셀 정보를 반환하는 함수
    """
    # 서비스 계정 인증
    credentials = Credentials.from_service_account_file(
        service_account_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    # 스프레드시트 메타데이터 가져오기
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    sheet_names = [sheet['properties']['title'] for sheet in sheets]

    if sheet_name not in sheet_names:
        raise ValueError(f"Sheet '{sheet_name}' does not exist in the spreadsheet.")
    
    # 특정 시트 데이터 가져오기
    range_name = f"{sheet_name}"
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_name
    ).execute()
    
    # 데이터프레임 변환
    df = pd.DataFrame(result.get('values', []))
    df.columns = df.loc[0]  # 첫 번째 행을 열 이름으로 설정
    df = df[1:]  # 첫 번째 행 제거
    df = df.set_index(df.columns[0])  # 첫 번째 열을 인덱스로 설정
    
    # 빈 셀 위치 확인
    empty_cells = df.isna() | (df == "")
    empty_locations = empty_cells.stack()[empty_cells.stack()].index.tolist()

    # 빈 셀 딕셔너리 생성
    empty_space_dict = {}
    for items in empty_locations:
        key = items[0]
        value = items[1]
        if key in empty_space_dict:
            empty_space_dict[key].append(value)
        else:
            empty_space_dict[key] = [value]

    return empty_space_dict

@app.route('/read-google-sheet/<sheet_name>', methods=['GET'])
def handle_read_google_sheet(sheet_name):
    """
    Google Sheets 데이터를 읽고 빈 셀 정보를 반환하는 API
    """
    try:
        # Google Sheets 데이터 읽기
        result = read_google_sheet(DEFAULT_SHEET_ID, SERVICE_ACCOUNT_PATH, sheet_name)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
