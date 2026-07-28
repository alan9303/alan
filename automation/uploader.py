"""다운로드한 엑셀 파일을 실제 웹사이트의 /upload 엔드포인트로 자동 전송하는 공통 모듈."""
import os
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

WEB_UPLOAD_URL = os.environ.get("WEB_UPLOAD_URL") or "https://alan9303.pythonanywhere.com/upload"
SITE_USER = os.environ.get("SITE_USER", "admin")
SITE_PASS = os.environ.get("SITE_PASS", "changeme")


def upload_to_web(file_path, source, warehouse_name):
    with open(file_path, "rb") as f:
        resp = requests.post(
            WEB_UPLOAD_URL,
            data={"warehouse_name": warehouse_name, "source": source},
            files={"excel_file": (os.path.basename(file_path), f)},
            auth=(SITE_USER, SITE_PASS),
            timeout=120,
        )
    resp.raise_for_status()
    print(f"웹 업로드 요청 완료 (status={resp.status_code}): {WEB_UPLOAD_URL}")
    return resp
