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


# 엑셀 출처별 컬럼 위치가 서로 달라서 출처마다 파싱 규칙을 따로 둠 (컬럼 인덱스는 0부터 시작)
SOURCE_CONFIGS = {
    "ecount": {
        "label": "이카운트",
        "skiprows": 2,
        "item_code_col": 0,
        "item_name_col": 1,
        "box_qty_col": 2,
        "stock_qty_col": 4,
        "location_col": None,
        "allowed_locations": None,
    },
    "emp": {
        "label": "EMP",
        "skiprows": 2,
        "item_code_col": 2,
        "item_name_col": 3,
        "box_qty_col": None,  # EMP 파일에는 박스입수량 컬럼이 없음
        "stock_qty_col": 13,
        "location_col": 9,
        "allowed_locations": {"온라인창고", "제품창고"},
    },
}


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
        source = request.form.get("source", "")

        if not file or file.filename == "":
            flash("엑셀 파일을 선택해주세요.")
            return redirect(url_for("upload"))
        if not warehouse_name:
            flash("창고명을 입력해주세요.")
            return redirect(url_for("upload"))
        config = SOURCE_CONFIGS.get(source)
        if config is None:
            flash("출처(이카운트/EMP)를 선택해주세요.")
            return redirect(url_for("upload"))

        df = pd.read_excel(file, header=None, skiprows=config["skiprows"])

        # 같은 품목코드가 여러 행(창고 위치별 등)으로 나뉘어 있을 수 있으므로 먼저 품목코드별로 합산
        aggregated = {}
        for _, row in df.iterrows():
            item_code = str(row[config["item_code_col"]]).strip() if pd.notna(row[config["item_code_col"]]) else ""
            if not item_code.isdigit():
                continue  # 합계/출력시각 등 품목이 아닌 요약행 제외 (품목코드는 숫자로만 구성됨)

            if config["location_col"] is not None:
                location = str(row[config["location_col"]]).strip() if pd.notna(row[config["location_col"]]) else ""
                if location not in config["allowed_locations"]:
                    continue

            item_name = str(row[config["item_name_col"]]).strip() if pd.notna(row[config["item_name_col"]]) else ""
            if config["box_qty_col"] is not None:
                box_qty = row[config["box_qty_col"]] if pd.notna(row[config["box_qty_col"]]) else 0
            else:
                box_qty = 0
            stock_qty = row[config["stock_qty_col"]] if pd.notna(row[config["stock_qty_col"]]) else 0

            if item_code in aggregated:
                aggregated[item_code]["stock_qty"] += stock_qty
            else:
                aggregated[item_code] = {
                    "item_name": item_name,
                    "box_qty": box_qty,
                    "stock_qty": stock_qty,
                }

        for item_code, data in aggregated.items():
            item = Item.query.filter_by(item_code=item_code, warehouse_name=warehouse_name).first()
            if item is None:
                item = Item(item_code=item_code, warehouse_name=warehouse_name)
                db.session.add(item)
            item.item_name = data["item_name"]
            item.box_qty = data["box_qty"]
            item.stock_qty = data["stock_qty"]

        db.session.commit()
        flash(f"{len(aggregated)}건 저장 완료 (창고: {warehouse_name}, 출처: {config['label']})")
        return redirect(url_for("upload"))

    recent_items = Item.query.order_by(Item.id.desc()).limit(20).all()
    return render_template("upload.html", items=recent_items, sources=SOURCE_CONFIGS)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=False)
