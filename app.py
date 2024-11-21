import requests
import os
import json
from flask import Flask, request, jsonify, render_template, redirect
from flask_cors import CORS
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import pandas as pd
from dotenv import load_dotenv
import re

# .env 파일 로드 (로컬 테스트용)
load_dotenv()

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app, resources={r"/*": {"origins": "*"}})

# 환경 변수 설정
DEFAULT_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_KEY = os.getenv("SERVICE_ACCOUNT_KEY")

cached_result = None

def read_google_sheet(sheet_id, sheet_name):
    global cached_result
    if cached_result:
        return cached_result  # 캐시된 데이터 반환
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
        cached_result = empty_space_dict  # 결과를 캐싱
        return empty_space_dict

    except json.JSONDecodeError as json_err:
        raise ValueError(f"서비스 계정 키 JSON 파싱 중 오류가 발생했습니다: {json_err}")
    except Exception as e:
        raise RuntimeError(f"Google Sheets API 호출 중 예기치 못한 오류가 발생했습니다: {str(e)}")

Authentication_dict = {'송정현' : '2022103121',
                       '김소륜' : '2022103110',
                       '임현우' : '2023102782',
                       '김가현' : '2023102759'
                       }

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # 로그인 페이지 렌더링
        return render_template('login.html')  # 로그인 페이지 반환

    elif request.method == 'POST':
        # POST 요청으로 사용자 정보 받기
        # JSON 데이터나 폼 데이터 중 가능한 데이터를 가져오기
        data = request.get_json() or request.form
        username = data.get('username')  # 사용자 이름
        student_id = data.get('student_id')  # 학번
        
        # 사용자 정보 검증
        if Authentication_dict[username] == student_id:
            # 사용자별 메시지 초기화
            student_info = f'{username}({student_id})'
            if student_info not in user_messages:
                user_messages[student_info] = []

            print(username)

            # 리다이렉트하여 /chat?username=홍길동 경로로 이동
            return jsonify({"success": True, "redirect": f"/chat?username={username}"}), 200
        else:
            # 데이터가 유효하지 않을 경우 오류 반환
            return jsonify({"success": False, "message": "사용자 이름과 학번을 입력해주세요."}), 400

# 전역 변수 선언: 사용자별 메시지 저장
user_messages = {}  # {username: [Messages]}

@app.route('/chat', methods=['GET', 'POST'])
def chat():

    if request.method == 'GET':
        # GET 요청: 초기 메시지를 렌더링
        username = request.args.get('username')  # 클라이언트에서 사용자 이름 전달
        if not username:
            return jsonify({"error": "사용자 이름이 필요합니다."}), 400
        print(username)

        # 사용자별 메시지 기록 초기화 (없으면 생성)
        if username not in user_messages:
            user_messages[username] = [
                {"role": "assistant", "content": "안녕하세요! 경영대 장소 대여 포털입니다. 원하는 날짜를 입력해주세요!"}
            ]

        # 전체 대화 기록을 반환
        Messages = user_messages[username]

        return render_template('chat.html', initial_message=Messages[-1]['content'])  # 초기 메시지 반환

    elif request.method == 'POST':
        """
        사용자별 채팅 처리 (POST 요청)
        """
        data = request.get_json()
        username = data.get('username')  # 요청 본문에서 username 가져오기

        if not username:
            return jsonify({"error": "사용자 이름이 필요합니다."}), 400

        min_people = data.get('minPeople')  # 최소 사용 인원 수
        userchat = data.get('userchat')  # 원하는 날짜
    
        # 프로젝트 및 API 관련 설정
        project_code = os.getenv("PROJECT_CODE")
        # api_key = "261122ab9932cbc5913ecef6b675a5e103ba585257f57039551bc7b86b2a6261"
        api_key = os.getenv("API_KEY")
        # hash = "94f768e1f3e1b8e560638d2d4cc3ed0f2edc280273911e5cd37150dbb1cb9435"
        hash = os.getenv("API_HASH")
        laas_chat_url = "https://api-laas.wanted.co.kr/api/preset/v2/chat/completions"

        headers = {
            "project": project_code,
            "apiKey": api_key,
            "Content-Type": "application/json; charset=utf-8"
        }

        Messages = user_messages[username]

        # Set the request
        data = {
            "hash": hash,
            "messages": Messages,
            "params": {
                "question": min_people
            }
        }


        # 최소 사용 인원과 날짜 확인
        if not min_people or not userchat:
            return jsonify({"error": "최소 사용 인원과 원하는 날짜 모두 필요합니다."}), 400

        # 사용자별 메시지 기록 가져오기 (없으면 초기화)
        if username not in user_messages:
            user_messages[username] = [
                {"role": "assistant", "content": "안녕하세요 오비스홀 공간대여 챗봇입니다. 원하시는 시간대와 최소 사용 인원을 입력해 주세요."}
            ]

        # 현재 사용자의 메시지 기록
        Messages = user_messages[username]

        # 사용자 입력을 메시지 형식으로 기록
        Messages.append({"role": "user", "content": f"최소 사용 인원: {min_people}, {userchat}"})


        try:
            # POST 요청 처리 로직
            response = requests.post(laas_chat_url, headers=headers, json=data)
            if response.status_code == 200:
                response_json = response.json()
                assistant_message_content = response_json['choices'][0]['message']['content']

                if '강의실을 찾았습니다.' in str(assistant_message_content):
                    match = re.search(r'\(.*?\)', str(assistant_message_content))
                    if match:
                        result_date = match.group()
                        result_dict = read_google_sheet(DEFAULT_SHEET_ID, result_date)
                        Messages.append({"role": "user", "content": f"강의실 빈 시간 리스트: {result_dict}"})

                print(assistant_message_content)
                assistant_message = {"role": "assistant", "content": assistant_message_content}
      
                # 어시스턴트 응답 추가
                Messages.append(assistant_message)
                # print(Messages)
                # 사용자별 메시지 기록 갱신
                user_messages[username] = Messages

                return jsonify(assistant_message)  # 어시스턴트의 최종 응답 반환
            else:
                return jsonify({"error": f"Failed with status code {response.status_code}"}), response.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Request failed", "details": str(e)}), 500
        
if __name__ == '__main__':  
    app.run('0.0.0.0', port=3000)