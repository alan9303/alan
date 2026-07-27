"""현재 마우스 좌표를 계속 출력하는 도우미 스크립트.
EMP 프로그램의 각 버튼/입력창 위에 마우스를 올려두고 좌표를 확인할 때 사용.
Ctrl+C로 종료.
"""
import time
import pyautogui

print("마우스를 원하는 위치로 이동하세요. Ctrl+C로 종료.")
try:
    while True:
        x, y = pyautogui.position()
        print(f"\rx={x}, y={y}", end="", flush=True)
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\n종료")
