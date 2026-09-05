from asyncio.log import logger
import json
import os
from openai import OpenAI
from qdrant_client import QdrantClient, models


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant_db:6333")
COLLECTION_NAME = "ecommerce_products"

ai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL)

# analyze query and return relevant products
def analyze_query(query: str, category: str = None, max_price: float = None, top_k: int = 4):
    # Dùng LLM để phân tích câu hỏi và trả về các tài liệu liên quan
    analyzer_prompt = """Bạn là một chuyên gia phân tích dữ liệu sản phẩm. Hãy đọc câu hỏi và trả về ĐÚNG 1 ĐỊNH DẠNG JSON.
    1. "category": "dien_tu" (điện thoại, tai nghe,...), "thoi_trang" (quần áo, balo,...), hoặc null nếu không rõ.
    2. "max_price": CHÚ Ý - Phải dịch các từ chỉ tiền tệ sang số nguyên VNĐ:
     - Ví dụ: "10 triệu", "10 củ" -> 10000000
     - Ví dụ: "500k", "500 cành" -> 500000
     - Ví dụ: "dưới 2 triệu" -> 2000000
     - Nếu câu hỏi không nhắc đến hạn giá tối đa -> null

     Trả về duy nhất JSON, không thêm bất kỳ text nào khác.
    """
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": analyzer_prompt},
                {"role": "user", "content": query}
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
    except Exception as e:
        logger.error(f"Lỗi phân tích query: {e}")
        return {"category": None, "max_price": None}


def retrieve_context(query: str, category: str = None, max_price: float = None, top_k: int = 4) -> str:
    """
    Tìm kiếm vector trong Qdrant kết hợp với bộ lọc Metadata (Danh mục, Giá).
    """
    try:
        # 1. Nhúng câu hỏi của người dùng thành Vector
        embed_res = ai_client.embeddings.create(
            input=query,
            model="text-embedding-3-small"
        )
        query_vector = embed_res.data[0].embedding

        # 2. Xây dựng bộ lọc Metadata (Pre-filtering)
        must_conditions = []

        # Lọc theo danh mục (Match chính xác)
        if category:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.category",
                    match=models.MatchValue(value=category)
                )
            )

        # Lọc theo khoảng giá (Nhỏ hơn hoặc bằng max_price)
        if max_price:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.price",
                    range=models.Range(lte=max_price) # lte: less than or equal
                )
            )

        # Đóng gói filter
        search_filter = models.Filter(must=must_conditions) if must_conditions else None

        # 3. Tìm kiếm Vector trên Qdrant (Chỉ quét các document thỏa mãn filter)
        search_results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k
        )
        print("Kết quả tìm kiếm từ Qdrant:", search_results)

        # reranking result
        # 4. Trích xuất nội dung text từ các chunk tìm được
        if not search_results.points:
            return ""

        context_chunks = [
            {
                "content": point.payload.get("content", ""),
                "price": point.payload.get("price") or point.payload.get("metadata", {}).get("price", 0),
                "type": point.payload.get("type") or point.payload.get("metadata", {}).get("type", "product_info"),
                "score": point.score,
                "metadata": point.payload
            }
            for point in search_results.points
        ]

        logger.info("Context chunks: %s", context_chunks)

        formatted_contexts = []
        for chunk in context_chunks:
            # Kiểm tra type: Nếu là chính sách thì không hiện giá
            if chunk['type'] == 'policy':
                combined_text = f"[CHÍNH SÁCH CỬA HÀNG]\n{chunk['content']}"
            else:
                # Nếu là sản phẩm thì mới format giá
                formatted_price = f"{chunk['price']:,.0f}".replace(",", ".")
                combined_text = f"[SẢN PHẨM]\n{chunk['content']}\nGiá bán: {formatted_price} VNĐ"

            formatted_contexts.append(combined_text)

        # Nối các khối lại, dùng phân cách rõ ràng để LLM không bị lẫn lộn các đoạn
        context_text = "\n\n" + "="*30 + "\n\n".join(formatted_contexts) + "\n\n" + "="*30

        logger.info(f"Context Text gửi cho LLM:\n{context_text}")

        return context_text

    except Exception as e:
        logger.error(f"Lỗi khi truy xuất Qdrant: {e}")
        return ""

def generate_answer_stream(query: str, category: str = None, max_price: float = None):
    """
        Generate function: Gọi retrieval_context từ dữ liệu, sau đó stream kết quả từ LLM về.
    """

    # Bước 1: Rút trích ngữ cảnh từ Database
    context = retrieve_context(query, category, max_price)

    # Xử lý trường hợp Database trống hoặc không tìm thấy sản phẩm phù hợp
    if not context:
        yield "Xin lỗi, hiện tại chúng tôi không tìm thấy sản phẩm phù hợp với yêu cầu của bạn."
        return

    # Bước 2: Xây dựng System Prompt chặt chẽ
    system_prompt = """Bạn là trợ lý ảo AI xuất sắc của hệ thống E-commerce.
    QUY TẮC BẮT BUỘC:
    1. Thông tin trong [NGỮ CẢNH SẢN PHẨM] là các sản phẩm ĐÃ ĐƯỢC HỆ THỐNG LỌC CHUẨN XÁC theo mức giá và danh mục khách yêu cầu.
    2. Hãy TỰ TIN giới thiệu các sản phẩm này. TUYỆT ĐỐI KHÔNG được nói là "không có sản phẩm nào phù hợp" nếu trong ngữ cảnh có chứa sản phẩm.
    3. KHÔNG tự ý so sánh toán học (lớn hơn, nhỏ hơn). Chỉ trình bày lại tên, mô tả và giá tiền của sản phẩm. Nếu có nhiều sản phẩm trong ngữ cảnh, hãy trình bày một cách thân thiện.
    4. Nếu [NGỮ CẢNH SẢN PHẨM] hoàn toàn trống, lúc đó mới lịch sự xin lỗi khách hàng.

    [NGỮ CẢNH SẢN PHẨM]:
    {context_data}
    """

    # Bước 3: Gọi API OpenAI với chế độ Streaming
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt.format(context_data=context)},
                {"role": "user", "content": query}
            ],
            stream=True,
            temperature=0.1 # Để siêu thấp để AI bám sát dữ liệu
        )

        # Trả về từng chữ ngay khi OpenAI phản hồi
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"Lỗi khi gọi OpenAI API: {e}")
        yield "Hệ thống AI đang quá tải, vui lòng thử lại sau giây lát."
