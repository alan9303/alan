"""이름을 붙여서 좌표를 하나씩 캡처하는 도우미 스크립트.
각 항목 위치에 마우스를 올려둔 채로 콘솔에서 Enter를 누르면 그 순간 좌표가 기록된다.
마지막에 전체 결과를 한 번에 출력한다.
"""
import pyautogui

LABELS = [
    "아이디 입력칸",
    "비밀번호 입력칸",
    "로그인 버튼",
]

results = {}
for label in LABELS:
    input(f"[{label}] 위치에 마우스를 올려두고 Enter를 누르세요...")
    x, y = pyautogui.position()
    results[label] = (x, y)
    print(f"  -> 기록됨: x={x}, y={y}")

print("\n=== 전체 결과 ===")
for label, (x, y) in results.items():
    print(f"{label}: x={x}, y={y}")
