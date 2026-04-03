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
                    measured_time_str = dt_kst.strftime("%Y-%m-%d %H:%M")
                except:
                    measured_time_str = str(ts)
            else:
                measured_time_str = now_kst.strftime("%Y-%m-%d %H:%M") 

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

# 6. CSV 파일로 저장 (클라우드 현재 폴더에 저장되도록 파일명만 씁니다)
df = pd.DataFrame(processed_data)[["측정시간", "장비명", "℃", "%rF"]]
df = df.sort_values(by="장비명", ascending=True)

file_path = "Saveris_Data.csv"

if not os.path.exists(file_path):
    df.to_csv(file_path, index=False, mode='w', encoding='utf-8-sig')
else:
    df.to_csv(file_path, index=False, mode='a', header=False, encoding='utf-8-sig')