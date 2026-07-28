"""이카운트ERP에 로그인해서 재고현황 엑셀을 다운로드하는 스크립트.

기준일자를 (오늘 + 1개월)로 맞춰서 검색한 뒤 엑셀로 받는다.
받은 파일은 uploads 폴더로 이동시키고, 창고명(송림특판)과 날짜를 파일명에 붙인다.
"""
import os
import time
import glob
from datetime import date
from dateutil.relativedelta import relativedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

from uploader import upload_to_web

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
WAREHOUSE_NAME = "송림특판"

load_dotenv(os.path.join(BASE_DIR, ".env"))

MONTH_SEL = r"#mainPage > div.header.header-fixed > div.wrapper-header-search > div.tab-content > div:nth-child(1) > ul > li:nth-child(1) > div.form > div:nth-child(2) > div > div.wrapper-datepicker.\{\{style\.contextCss\}\} > button:nth-child(4)"
YEAR_SEL = r"#mainPage > div.header.header-fixed > div.wrapper-header-search > div.tab-content > div:nth-child(1) > ul > li:nth-child(1) > div.form > div:nth-child(2) > div > div.wrapper-datepicker.\{\{style\.contextCss\}\} > button:nth-child(1)"


def wait_for_new_file(folder, before_files, timeout=30):
    end_time = time.time() + timeout
    while time.time() < end_time:
        after_files = set(glob.glob(os.path.join(folder, "*")))
        new_files = after_files - before_files
        finished = [f for f in new_files if not f.endswith(".crdownload")]
        if finished:
            return finished[0]
        time.sleep(0.5)
    raise TimeoutError("다운로드 완료를 기다렸지만 새 파일을 찾지 못했습니다.")


def download_ecount_stock_excel():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_experimental_option("prefs", {
        "download.default_directory": UPLOAD_DIR,
        "download.prompt_for_download": False,
    })
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        driver.get("https://login.ecount.com/LOGIN")
        time.sleep(2)
        driver.find_element(By.ID, "com_code").send_keys(os.environ["ECOUNT_COMPANY_CODE"])
        driver.find_element(By.ID, "id").send_keys(os.environ["ECOUNT_ID"])
        driver.find_element(By.ID, "passwd").send_keys(os.environ["ECOUNT_PW"])
        driver.find_element(By.ID, "save").click()

        # 새로운 기기 로그인 알림 팝업이 먼저 뜸 - 등록을 눌러야 다음 실행부터 팝업이 뜨지 않음
        try:
            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-item-key='regist_footer_toolbar']"))
            ).click()
        except Exception:
            pass

        # 팝업 처리 후 대시보드의 메뉴검색 입력창을 기다림
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='메뉴검색']")))
        except Exception:
            driver.save_screenshot(os.path.join(BASE_DIR, "debug_after_login.png"))
            raise
        search_box = driver.find_element(By.CSS_SELECTOR, "input[placeholder='메뉴검색']")
        search_box.click()
        search_box.send_keys("재고현황")

        try:
            menu_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@id, 'MPMU00000100043')]")))
            menu_item.click()
        except Exception:
            driver.save_screenshot(os.path.join(BASE_DIR, "debug_menu_search.png"))
            raise

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchGroup")))
        time.sleep(2)

        # 기준일자를 (오늘 + 1개월)로 변경
        target_date = date.today() + relativedelta(months=1)
        today = date.today()

        if target_date.year != today.year:
            driver.find_element(By.CSS_SELECTOR, YEAR_SEL).click()
            time.sleep(1)
            driver.find_element(By.XPATH, f"//*[normalize-space(text())='{target_date.year}']").click()
            time.sleep(1)

        if target_date.month != today.month:
            driver.find_element(By.CSS_SELECTOR, MONTH_SEL).click()
            time.sleep(1)
            driver.find_element(By.XPATH, f"//*[normalize-space(text())='{target_date.month}월']").click()
            time.sleep(1)

        # 검색(F8)
        driver.find_element(By.CSS_SELECTOR, "#searchGroup").click()
        time.sleep(4)

        # 엑셀 다운로드
        before_files = set(glob.glob(os.path.join(UPLOAD_DIR, "*")))
        driver.find_element(By.CSS_SELECTOR, "#outputExcel").click()
        downloaded_path = wait_for_new_file(UPLOAD_DIR, before_files)

        # 창고명 + 날짜로 파일명 정리
        ext = os.path.splitext(downloaded_path)[1]
        new_name = f"{WAREHOUSE_NAME}_재고현황_{today.strftime('%Y%m%d')}{ext}"
        new_path = os.path.join(UPLOAD_DIR, new_name)
        if os.path.exists(new_path):
            os.remove(new_path)
        os.rename(downloaded_path, new_path)

        print(f"다운로드 완료: {new_path}")

        upload_to_web(new_path, source="ecount", warehouse_name=WAREHOUSE_NAME)

        return new_path
    finally:
        driver.quit()


if __name__ == "__main__":
    download_ecount_stock_excel()
