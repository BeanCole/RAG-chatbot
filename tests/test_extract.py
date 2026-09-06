import json

from sqlalchemy import create_engine, text

from app.pipeline import extract


def _sqlite_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE products ("
                "product_id INTEGER PRIMARY KEY, name TEXT, description TEXT, "
                "category TEXT, price REAL, status TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO products VALUES "
                "(1, 'Balo', 'vải dù', 'thoi_trang', 450000, 'active'), "
                "(2, 'Tai nghe', NULL, NULL, NULL, 'active'), "
                "(3, 'Cũ', 'x', 'dien_tu', 100, 'inactive')"
            )
        )
    return engine


def test_extract_maps_rows_and_skips_inactive(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "get_engine", _sqlite_engine)
    out = tmp_path / "raws.jsonl"

    count = extract.extract_products_data_to_jsonl(str(out))

    docs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert count == 2
    assert {d["doc_id"] for d in docs} == {"prod_1", "prod_2"}

    by_id = {d["doc_id"]: d for d in docs}
    assert by_id["prod_2"]["metadata"]["category"] == "uncategorized"
    assert by_id["prod_2"]["metadata"]["price"] == 0.0
    assert "Không có mô tả chi tiết" in by_id["prod_2"]["content"]
    assert by_id["prod_1"]["metadata"]["type"] == "product_info"
