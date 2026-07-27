"""EMP(Enhanced Management Plus) 클라이언트 프로그램에서 재고자료를 다운로드하는 스크립트.

EMP는 웹사이트가 아니라 데스크톱 프로그램이라 셀렉터를 쓸 수 없어서,
화면 좌표를 클릭하는 방식(pyautogui)으로 자동화한다.
저장 대화상자가 뜨면 스크립트가 전체 경로를 직접 타이핑해서 저장까지 자동으로 끝낸다.

주의: 이 스크립트가 실행되는 동안에는 마우스/키보드를 건드리면 안 된다 (화면 좌표 기준 클릭이라 흐트러짐).
"""
import os
import time
import glob
from datetime import date

import pyautogui
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAREHOUSE_NAME = "수태공장"

load_dotenv(os.path.join(BASE_DIR, ".env"))

# 작업용 PC에서는 .env의 DOWNLOAD_DIR로 저장 위치를 지정할 수 있음 (미설정 시 프로젝트 uploads 폴더 사용)
UPLOAD_DIR = os.environ.get("DOWNLOAD_DIR", os.path.join(BASE_DIR, "uploads"))

EMP_EXE_PATH = os.environ["EMP_EXE_PATH"]
EMP_ID = os.environ["EMP_ID"]
EMP_PW = os.environ["EMP_PW"]

# 화면 좌표 (capture_coordinates.py로 확인한 값). 모니터 배치/해상도가 바뀌면 다시 캡처해야 함.
ID_FIELD = (988, 461)
PW_FIELD = (988, 489)
LOGIN_BTN = (973, 533)
UPDATE_BTN = (1100, 540)
SELECT_BTN = (952, 554)
MENU_SEARCH_BOX = (292, 239)
STOCK_STATUS_MENU_ITEM = (1000, 384)
EXCEL_EXPORT_BTN = (772, 76)


def wait_for_new_file(folder, before_files, timeout=60):
    end_time = time.time() + timeout
    while time.time() < end_time:
        after_files = set(glob.glob(os.path.join(folder, "*")))
        new_files = after_files - before_files
        finished = [f for f in new_files if not f.endswith((".crdownload", ".tmp"))]
        if finished:
            return finished[0]
        time.sleep(0.5)
    raise TimeoutError("다운로드 완료를 기다렸지만 새 파일을 찾지 못했습니다.")


def download_emp_stock_excel():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    os.startfile(EMP_EXE_PATH)
    time.sleep(8)  # 프로그램 실행 대기

    pyautogui.click(*ID_FIELD)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(EMP_ID, interval=0.03)

    pyautogui.click(*PW_FIELD)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(EMP_PW, interval=0.03)

    pyautogui.click(*LOGIN_BTN)

    time.sleep(10)  # 로그인 처리 대기
    pyautogui.click(*UPDATE_BTN)

    time.sleep(20)  # 업데이트 대기
    pyautogui.click(*SELECT_BTN)

    time.sleep(2)
    pyautogui.click(*MENU_SEARCH_BOX)
    pyautogui.typewrite("재고", interval=0.05)
    pyautogui.press("enter")

    time.sleep(1.5)
    pyautogui.doubleClick(*STOCK_STATUS_MENU_ITEM)

    time.sleep(3)
    pyautogui.press("f2")

    time.sleep(20)  # 재고 조회 대기
    pyautogui.click(*EXCEL_EXPORT_BTN)

    # 엑셀 저장 대화상자 - 파일명 입력란에 전체 경로를 직접 입력해서 저장 (사람이 타이핑하지 않음, 스크립트가 자동 입력)
    time.sleep(2)
    today = date.today()
    save_name = f"{WAREHOUSE_NAME}_재고현황_{today.strftime('%Y%m%d')}.xlsx"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    if os.path.exists(save_path):
        os.remove(save_path)

    before_files = set(glob.glob(os.path.join(UPLOAD_DIR, "*")))

    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(save_path, interval=0.01)
    pyautogui.press("enter")

    time.sleep(2)
    pyautogui.press("enter")  # 덮어쓰기/형식 확인 대화상자 대비

    downloaded_path = wait_for_new_file(UPLOAD_DIR, before_files)
    print(f"다운로드 완료: {downloaded_path}")
    return downloaded_path


if __name__ == "__main__":
    download_emp_stock_excel()
