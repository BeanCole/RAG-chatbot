import json

from app.pipeline.transform import transform_jsonl_to_chunks


def _write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
    )


def test_transform_writes_ordered_unique_chunks(tmp_path):
    raws = tmp_path / "raws.jsonl"
    out = tmp_path / "chunks.jsonl"
    _write_jsonl(
        raws,
        [
            {
                "doc_id": "prod_1",
                "content": "Tên sản phẩm: Balo\nMô tả: " + "vải dù " * 200,
                "metadata": {"type": "product_info", "category": "thoi_trang"},
            },
            {
                "doc_id": "prod_2",
                "content": "Tên sản phẩm: Tai nghe\nMô tả: chống ồn",
                "metadata": {"type": "product_info", "category": "dien_tu"},
            },
        ],
    )

    count = transform_jsonl_to_chunks(str(raws), str(out))

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert count == len(lines)
    chunk_ids = [json.loads(line)["chunk_id"] for line in lines]
    assert len(chunk_ids) == len(set(chunk_ids))
    assert chunk_ids == sorted(
        chunk_ids, key=lambda c: (c.split("_chunk_")[0], int(c.split("_chunk_")[1]))
    )


def test_transform_skips_blank_lines(tmp_path):
    raws = tmp_path / "raws.jsonl"
    out = tmp_path / "chunks.jsonl"
    raws.write_text(
        json.dumps({"doc_id": "prod_1", "content": "x", "metadata": {}}) + "\n\n",
        encoding="utf-8",
    )
    assert transform_jsonl_to_chunks(str(raws), str(out)) == 1
