from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import pandas as pd
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "instance", "inventory.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

db = SQLAlchemy(app)

SITE_USER = os.environ.get("SITE_USER", "admin")
SITE_PASS = os.environ.get("SITE_PASS", "changeme")


@app.before_request
def require_login():
    auth = request.authorization
    valid = auth and secrets.compare_digest(auth.username, SITE_USER) and secrets.compare_digest(auth.password, SITE_PASS)
    if not valid:
        return Response(
            "로그인이 필요합니다.", 401, {"WWW-Authenticate": 'Basic realm="Inventory"'}
        )


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    box_qty = db.Column(db.Float, default=0)
    stock_qty = db.Column(db.Float, default=0)
    warehouse_name = db.Column(db.String(100), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("item_code", "warehouse_name", name="uq_item_warehouse"),
    )


@app.route("/")
def hello_world():
    return "Hello World! Flask 서버가 정상적으로 실행되고 있습니다."


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    warehouse = request.args.get("warehouse", "").strip()

    warehouses = [
        row[0] for row in db.session.query(Item.warehouse_name).distinct().order_by(Item.warehouse_name).all()
    ]

    results = []
    if query:
        keyword_filter = db.or_(Item.item_code.contains(query), Item.item_name.contains(query))

        if warehouse:
            rows = (
                Item.query.filter(keyword_filter, Item.warehouse_name == warehouse)
                .order_by(Item.item_code)
                .all()
            )
            results = [
                {
                    "item_code": r.item_code,
                    "item_name": r.item_name,
                    "box_qty": r.box_qty,
                    "stock_qty": r.stock_qty,
                    "warehouse_name": r.warehouse_name,
                }
                for r in rows
            ]
        else:
            # 창고 필터가 없으면 품목코드 기준으로 합쳐서 전체 재고 합계를 보여줌
            rows = (
                db.session.query(
                    Item.item_code,
                    Item.item_name,
                    Item.box_qty,
                    db.func.sum(Item.stock_qty).label("total_stock"),
                    db.func.group_concat(Item.warehouse_name, ", ").label("warehouse_names"),
                )
                .filter(keyword_filter)
                .group_by(Item.item_code)
                .order_by(Item.item_code)
                .all()
            )
            results = [
                {
                    "item_code": r.item_code,
                    "item_name": r.item_name,
                    "box_qty": r.box_qty,
                    "stock_qty": r.total_stock,
                    "warehouse_name": r.warehouse_names,
                }
                for r in rows
            ]

    return render_template(
        "search.html", results=results, query=query, warehouse=warehouse, warehouses=warehouses
    )


@app.route("/db-check")
def db_check():
    try:
        item_count = Item.query.count()
        return f"DB 연결 성공! 현재 저장된 품목 수: {item_count}개"
    except Exception as e:
        return f"DB 연결 실패: {e}"


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("excel_file")
        warehouse_name = request.form.get("warehouse_name", "").strip()

        if not file or file.filename == "":
            flash("엑셀 파일을 선택해주세요.")
            return redirect(url_for("upload"))
        if not warehouse_name:
            flash("창고명을 입력해주세요.")
            return redirect(url_for("upload"))

        # 1행: 회사명/기준일자 제목, 2행: 헤더, 3행부터 데이터 -> 앞 2행 건너뛰기
        df = pd.read_excel(file, header=None, skiprows=2)

        saved_count = 0
        for _, row in df.iterrows():
            item_code = str(row[0]).strip() if pd.notna(row[0]) else ""
            if not item_code.isdigit():
                continue  # 합계/출력시각 등 품목이 아닌 요약행 제외 (품목코드는 숫자로만 구성됨)
            item_name = str(row[1]).strip() if pd.notna(row[1]) else ""
            box_qty = row[2] if pd.notna(row[2]) else 0
            stock_qty = row[4] if pd.notna(row[4]) else 0

            item = Item.query.filter_by(item_code=item_code, warehouse_name=warehouse_name).first()
            if item is None:
                item = Item(item_code=item_code, warehouse_name=warehouse_name)
                db.session.add(item)
            item.item_name = item_name
            item.box_qty = box_qty
            item.stock_qty = stock_qty
            saved_count += 1

        db.session.commit()
        flash(f"{saved_count}건 저장 완료 (창고: {warehouse_name})")
        return redirect(url_for("upload"))

    recent_items = Item.query.order_by(Item.id.desc()).limit(20).all()
    return render_template("upload.html", items=recent_items)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=False)
