import os
import json
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import pandas as pd
from dotenv import load_dotenv

# .env 파일 로드 (로컬 테스트용)
load_dotenv()

# 환경 변수 설정
DEFAULT_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_KEY = os.getenv("SERVICE_ACCOUNT_KEY")

# Flask 앱 정의
app = Flask(__name__)

def read_google_sheet(sheet_id, sheet_name):
    try:
        # JSON 데이터를 환경 변수에서 로드
        service_account_info = json.loads(SERVICE_ACCOUNT_KEY)
        service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")  # 줄바꿈 처리

        # Google API 인증
        credentials = Credentials.from_service_account_info(
            service_account_info,
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
    except json.JSONDecodeError as json_err:
        raise ValueError(f"서비스 계정 키 JSON 파싱 중 오류가 발생했습니다: {json_err}")
    except Exception as e:
        raise RuntimeError(f"Google Sheets API 호출 중 예기치 못한 오류가 발생했습니다: {str(e)}")


@app.route('/read-google-sheet/<sheet_name>', methods=['GET'])
def handle_read_google_sheet(sheet_name):
    try:
        # Google Sheets 데이터 읽기
        result = read_google_sheet(DEFAULT_SHEET_ID, sheet_name)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except RuntimeError as re:
        return jsonify({"error": str(re)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

# Vercel 엔트리포인트 추가
def handler(event, context):
    from serverless_wsgi import handle_request
    return handle_request(app, event, context)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
