import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from io import StringIO
import re
import os
import time

# ===================== 1. API 설정 =====================
REGION = "ap"  # ⚠️ 첫 실행 후 연결 오류 시 "eu" 등으로 교체 필요할 수 있음
BASE_URL = f"https://data-api.{REGION}.smartconnect.testo.com"
API_KEY = os.environ.get("SAVERIS_TOKEN")

HEADERS = {
    "x-custom-api-key": API_KEY,
    "Content-Type": "application/json"
}

# ===================== 2. 조회 구간 설정 (최근 1시간, UTC 기준) =====================
now_kst = datetime.now(timezone(timedelta(hours=9)))
print(f"▶ 봇 실행 시간: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")

now_utc = datetime.now(timezone.utc)
date_from = (now_utc - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
date_until = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

# ===================== 3. 비동기 요청: 제출 → 폴링(20초 간격) → 다운로드 =====================
def fetch_measurements_csv():
    submit_body = {
        "date_time_from": date_from,
        "date_time_until": date_until,
        "options": {"result_file_format": "CSV"}
    }
    submit_res = requests.post(f"{BASE_URL}/v2/measurements", headers=HEADERS, json=submit_body)
    print("▶ 제출 응답 코드:", submit_res.status_code)
    print("▶ 제출 응답 내용:", submit_res.text[:500])

    if submit_res.status_code not in (200, 201, 202):
        print("❌ 데이터 요청 제출 실패")
        exit()

    request_uuid = submit_res.json().get("request_uuid")
    if not request_uuid:
        print("❌ request_uuid를 받지 못했습니다")
        exit()

    for attempt in range(15):  # 20초 x 15회 = 최대 5분 대기
        time.sleep(20)
        status_res = requests.get(f"{BASE_URL}/v2/measurements/{request_uuid}", headers=HEADERS)
        status_json = status_res.json()
        status = status_json.get("status")
        print(f"▶ 폴링 {attempt+1}회차 상태: {status}")

        if status == "Completed":
            data_urls = status_json.get("data_urls", [])
            if not data_urls:
                print("❌ 완료됐지만 다운로드 URL이 없습니다")
                exit()
            csv_res = requests.get(data_urls[0])
            csv_res.encoding = 'utf-8'
            return csv_res.text
        elif status in ("Failed", "Error"):
            print("❌ 데이터 준비 실패:", status_json)
            exit()

    print("❌ 시간 초과: 데이터가 준비되지 않았습니다")
    exit()

csv_text = fetch_measurements_csv()

# ===================== 4. CSV 파싱 (최초 실행 시 실제 컬럼명 확인용 로그) =====================
raw_df = pd.read_csv(StringIO(csv_text))
print("▶ 수신된 CSV 컬럼:", list(raw_df.columns))
print("▶ 샘플 데이터:")
print(raw_df.head(3).to_string())

# ===================== 5. 컬럼명 매핑 (⚠️ 4번 로그 확인 후 실제 값으로 수정 필요) =====================
COL_TIME = "measured_at"
COL_NAME = "measuring_object_name"
COL_VALUE = "physical_value"
COL_UNIT = "physical_unit"

missing_cols = [c for c in [COL_TIME, COL_NAME, COL_VALUE, COL_UNIT] if c not in raw_df.columns]
if missing_cols:
    print(f"❌ 예상 컬럼이 CSV에 없습니다: {missing_cols}")
    print("▶ 위 4번 로그의 실제 컬럼명으로 이 섹션을 수정해 주세요.")
    exit()

# ===================== 6. 조건부 필터링 및 그룹핑 (측정값 자체 시각 기준) =====================
grouped_data = {}

for _, row in raw_df.iterrows():
    full_name = str(row[COL_NAME]).strip()
    match = re.search(r'^([A-Z])-\(.*?\)', full_name)
    if not match:
        continue

    group_id = match.group(1)
    display_name = match.group(0)

    try:
        row_time_utc = pd.to_datetime(row[COL_TIME], utc=True)
        row_time_kst = row_time_utc.tz_convert(timezone(timedelta(hours=9)))
    except Exception:
        continue

    is_weekday = row_time_kst.weekday() < 5
    is_working_hour = 9 <= row_time_kst.hour <= 17

    should_save = False
    if group_id in ['A', 'B']:
        should_save = True
    elif group_id in ['C', 'D', 'E', 'F', 'G']:
        if is_weekday and is_working_hour:
            should_save = True

    if not should_save:
        continue

    measured_time_str = row_time_kst.strftime("%Y-%m-%dT%H:00:00Z")
    key = (display_name, measured_time_str)

    if key not in grouped_data:
        grouped_data[key] = {"측정시간": measured_time_str, "장비명": display_name, "℃": None, "%rF": None}

    unit = str(row[COL_UNIT])
    val = row[COL_VALUE]
    if pd.isna(val):
        continue

    if unit in ('°C', 'C', 'DEG_C'):
        grouped_data[key]["℃"] = float(val)
    elif unit in ('%rF', 'RH', '%RH'):
        grouped_data[key]["%rF"] = float(val)

processed_data = list(grouped_data.values())

if not processed_data:
    print("▶ 현재 수집 조건에 맞는 장비가 없어 저장하지 않습니다.")
    exit()

# ===================== 7. CSV 저장 (중복 방지, 기존과 동일) =====================
df = pd.DataFrame(processed_data)[["측정시간", "장비명", "℃", "%rF"]]
df = df.sort_values(by="장비명", ascending=True)

file_path = "Saveris_Data.csv"

if os.path.exists(file_path):
    existing_df = pd.read_csv(file_path)
    new_rows = []
    for _, row in df.iterrows():
        is_duplicate = ((existing_df['측정시간'] == row['측정시간']) & (existing_df['장비명'] == row['장비명'])).any()
        if not is_duplicate:
            new_rows.append(row)
    if new_rows:
        pd.DataFrame(new_rows).to_csv(file_path, index=False, mode='a', header=False, encoding='utf-8-sig')
        print(f"▶ {len(new_rows)}건의 새로운 데이터를 추가했습니다.")
    else:
        print("▶ 이미 기록된 데이터입니다. 중복 저장을 건너뜁니다.")
else:
    df.to_csv(file_path, index=False, mode='w', encoding='utf-8-sig')
    print("▶ 새 데이터 파일을 생성했습니다.")
