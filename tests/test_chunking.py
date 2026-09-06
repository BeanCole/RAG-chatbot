from app.services.chunking import product_content, split_document


def test_product_content_handles_missing_description():
    assert "Không có mô tả chi tiết" in product_content("Balo", None)
    assert "vải dù" in product_content("Balo", "vải dù")


def test_split_document_enriches_product_chunks():
    records = split_document(
        "Tên sản phẩm: Balo\nMô tả: chống nước",
        "prod_1",
        {"type": "product_info", "category": "thoi_trang", "price": 450000.0},
    )
    assert records
    assert all(r["content"].startswith("[Thuộc sản phẩm id prod_1]") for r in records)
    assert [r["chunk_id"] for r in records] == [
        f"prod_1_chunk_{i}" for i in range(len(records))
    ]


def test_split_document_leaves_policy_chunks_untouched():
    records = split_document("Đổi trả trong 7 ngày", "policy_1", {"type": "policy"})
    assert records[0]["content"] == "Đổi trả trong 7 ngày"


def test_split_document_is_deterministic():
    args = ("a " * 400, "prod_9", {"type": "product_info"})
    assert split_document(*args) == split_document(*args)
