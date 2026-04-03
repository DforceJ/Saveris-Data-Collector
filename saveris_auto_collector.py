import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import re
import os

# 1. API 설정 (클라우드 비밀 금고에서 토큰을 가져옵니다)
BASE_URL = "https://apac.saveris.net/SaverisConnector/ws/api"
YOUR_JWT_TOKEN = os.environ.get("SAVERIS_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {YOUR_JWT_TOKEN}",
    "Content-Type": "application/json"
}

# 2. 실행 시간 및 수집 조건 확인
now_kst = datetime.now(timezone(timedelta(hours=9)))
current_hour = now_kst.hour        
current_weekday = now_kst.weekday() 

is_weekday = current_weekday < 5 
is_working_hour = 9 <= current_hour <= 17

print(f"▶ 봇 실행 시간: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")

# 3. 장비 목록 가져오기
points_response = requests.get(f"{BASE_URL}/saveris/v1/measuringPoint", headers=HEADERS)
if points_response.status_code != 200:
    print("❌ 장비 목록 조회 실패")
    exit()

measuring_points = points_response.json().get('measuringPoints', [])
id_to_name = {p['id']: p.get('name', '이름 없음') for p in measuring_points if 'id' in p}
all_ids = list(id_to_name.keys())

# 4. 최신 측정 데이터 가져오기
params = {'ids': ",".join(all_ids)}
data_response = requests.get(f"{BASE_URL}/saveris/v1/measuringPoint/value", headers=HEADERS, params=params)
latest_values = data_response.json().get('measuringPoints', [])

# 5. 조건부 데이터 필터링 및 병합
grouped_data = {} 

for item in latest_values:
    pid = item.get('measuringPointId')
    val = item.get('value')
    unit = item.get('unit')
    ts = item.get('timestamp') 
    
    if pid and val is not None:
        full_name = id_to_name.get(pid, str(pid)).strip()
        
        match = re.search(r'^([A-Z])-\(.*?\)', full_name)
        if not match: 
            continue
            
        group_id = match.group(1)   
        display_name = match.group(0)
        
        should_save = False
        if group_id in ['A', 'B']:
            should_save = True
        elif group_id in ['C', 'D', 'E', 'F', 'G']:
            if is_weekday and is_working_hour:
                should_save = True
                
if should_save:
            measured_time_str = None
            if ts:
                try:
                    ts_float = float(ts)
                    dt_utc = datetime.fromtimestamp(ts_float / 1000.0, tz=timezone.utc)
                    dt_kst = dt_utc.astimezone(timezone(timedelta(hours=9)))
                    
                    # 🚀 변경 1: 실제 분(%M)을 무시하고 무조건 '00'으로 강제 고정
                    measured_time_str = dt_kst.strftime("%Y-%m-%d %H:00") 
                    
                except:
                    measured_time_str = str(ts)
            else:
                
                # 🚀 변경 2: 위와 동일하게 '00'으로 강제 고정
                measured_time_str = now_kst.strftime("%Y-%m-%d %H:00")

            if display_name not in grouped_data:
                grouped_data[display_name] = {
                    "측정시간": measured_time_str, 
                    "장비명": display_name,
                    "℃": None,
                    "%rF": None
                }
            
            if unit == '°C':
                grouped_data[display_name]["℃"] = float(val)
            elif unit == '%rF':
                grouped_data[display_name]["%rF"] = float(val)

processed_data = list(grouped_data.values())

if not processed_data:
    print("▶ 현재 수집 조건에 맞는 장비가 없어 저장하지 않습니다.")
    exit()

# 6. CSV 파일로 저장 (중복 방지 로직 포함)
df = pd.DataFrame(processed_data)[["측정시간", "장비명", "℃", "%rF"]]
df = df.sort_values(by="장비명", ascending=True)

file_path = "Saveris_Data.csv"

if os.path.exists(file_path):
    existing_df = pd.read_csv(file_path)
    new_rows = []
    
    for _, row in df.iterrows():
        # 측정시간과 장비명이 모두 일치하는 데이터가 있는지 검사
        is_duplicate = ((existing_df['측정시간'] == row['측정시간']) & 
                        (existing_df['장비명'] == row['장비명'])).any()
        
        if not is_duplicate:
            new_rows.append(row)
            
    if new_rows:
        # 새로운 데이터만 파일 끝에 추가
        pd.DataFrame(new_rows).to_csv(file_path, index=False, mode='a', header=False, encoding='utf-8-sig')
        print(f"▶ {len(new_rows)}건의 새로운 데이터를 추가했습니다.")
    else:
        print("▶ 이미 기록된 데이터입니다. 중복 저장을 건너뜁니다.")
else:
    # 파일이 없으면 새로 생성
    df.to_csv(file_path, index=False, mode='w', encoding='utf-8-sig')
    print("▶ 새 데이터 파일을 생성했습니다.")
