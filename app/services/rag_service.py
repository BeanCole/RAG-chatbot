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
    # Dung LLM de phan tich cau hoi va tra ve cac tai lieu lien quan
    analyzer_prompt = """Báº¡n lÃ  má»™t chuyÃªn gia phÃ¢n tÃ­ch dá»¯ liá»‡u sáº£n pháº©m. HÃ£y Ä‘á»c cÃ¢u há»i vÃ  tráº£ vá» ÄÃšNG 1 Äá»ŠNH Dáº NG JSON.
    1. "category": "dien_tu" (Ä‘iá»‡n thoáº¡i, tai nghe,...), "thoi_trang" (quáº§n Ã¡o, balo,...), hoáº·c null náº¿u khÃ´ng rÃµ.
    2. "max_price": CHÃš Ã - Pháº£i dá»‹ch cÃ¡c tá»« chá»‰ tiá»n tá»‡ sang sá»‘ nguyÃªn VNÄ:
     - VÃ­ dá»¥: "10 triá»‡u", "10 cá»§" -> 1000000
     - VÃ­ dá»¥: "500k", "500 cÃ nh" -> 500000
     - VÃ­ dá»¥: "dÆ°á»›i 2 triá»‡u" -> 2000000
     - Náº¿u cÃ¢u há»i khÃ´ng nháº¯c Ä‘áº¿n háº¡n giÃ¡ tá»‘i Ä‘a -> null

     Tráº£ vá» duy nháº¥t JSON, khÃ´ng thÃªm báº¥t ká»³ text nÃ o khÃ¡c.
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
        logger.error(f"Lá»—i phÃ¢n tÃ­ch query: {e}")
        return {"category": None, "max_price": None}


def retrieve_context(query: str, category: str = None, max_price: float = None, top_k: int = 4) -> str:
    """
    TÃ¬m kiáº¿m vector trong Qdrant káº¿t há»£p vá»›i bá»™ lá»c Metadata (Danh má»¥c, GiÃ¡).
    """
    try:
        # 1. NhÃºng cÃ¢u há»i cá»§a ngÆ°á»i dÃ¹ng thÃ nh Vector
        embed_res = ai_client.embeddings.create(
            input=query,
            model="text-embedding-3-small"
        )
        query_vector = embed_res.data[0].embedding

        # 2. XÃ¢y dá»±ng bá»™ lá»c Metadata (Pre-filtering)
        must_conditions = []

        # Lá»c theo danh má»¥c (Match chÃ­nh xÃ¡c)
        if category:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.category",
                    match=models.MatchValue(value=category)
                )
            )

        # Lá»c theo khoáº£ng giÃ¡ (Nhá» hÆ¡n hoáº·c báº±ng max_price)
        if max_price:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.price",
                    range=models.Range(lte=max_price) # lte: less than or equal
                )
            )

        # ÄÃ³ng gÃ³i filter
        search_filter = models.Filter(must=must_conditions) if must_conditions else None

        # 3. TÃ¬m kiáº¿m Vector trÃªn Qdrant (Chá»‰ quÃ©t cÃ¡c document thá»a mÃ£n filter)
        search_results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k
        )
        print("Káº¿t quáº£ tÃ¬m kiáº¿m tá»« Qdrant:", search_results)

        # reranking result
        # 4. TrÃ­ch xuáº¥t ná»™i dung text tá»« cÃ¡c chunk tÃ¬m Ä‘Æ°á»£c
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
            # KIá»‚M TRA TYPE: Náº¿u lÃ  chÃ­nh sÃ¡ch thÃ¬ khÃ´ng hiá»‡n giÃ¡
            if chunk['type'] == 'policy':
                combined_text = f"[CHÃNH SÃCH Cá»¬A HÃ€NG]\n{chunk['content']}"
            else:
                # Náº¿u lÃ  sáº£n pháº©m thÃ¬ má»›i format giÃ¡
                formatted_price = f"{chunk['price']:,.0f}".replace(",", ".")
                combined_text = f"[Sáº¢N PHáº¨M]\n{chunk['content']}\nGiÃ¡ bÃ¡n: {formatted_price} VNÄ"

            formatted_contexts.append(combined_text)

        # Ná»‘i cÃ¡c khá»‘i láº¡i, dÃ¹ng phÃ¢n cÃ¡ch rÃµ rÃ ng Ä‘á»ƒ LLM khÃ´ng bá»‹ láº«n lá»™n cÃ¡c Ä‘oáº¡n
        context_text = "\n\n" + "="*30 + "\n\n".join(formatted_contexts) + "\n\n" + "="*30

        logger.info(f"Context Text gá»­i cho LLM:\n{context_text}")

        return context_text

    except Exception as e:
        logger.error(f"âŒ Lá»—i khi truy xuáº¥t Qdrant: {e}")
        return ""

def generate_answer_stream(query: str, category: str = None, max_price: float = None):
    """
        Generate function: Gá»i retrieval_context tá»« dá»¯ liá»‡u, sau Ä‘Ã³ stream káº¿t quáº£ tá»« LLM vá».
    """

    # BÆ°á»›c 1: RÃºt trÃ­ch ngá»¯ cáº£nh tá»« Database
    context = retrieve_context(query, category, max_price)

    # Xá»­ lÃ½ trÆ°á»ng há»£p Database trá»‘ng hoáº·c khÃ´ng tÃ¬m tháº¥y sáº£n pháº©m phÃ¹ há»£p
    if not context:
        yield "Xin lá»—i, hiá»‡n táº¡i chÃºng tÃ´i khÃ´ng tÃ¬m tháº¥y sáº£n pháº©m phÃ¹ há»£p vá»›i yÃªu cáº§u cá»§a báº¡n."
        return

    # BÆ°á»›c 2: XÃ¢y dá»±ng System Prompt cá»±c ká»³ cháº·t cháº½ (Prompt Engineering)
    system_prompt = """ Báº¡n lÃ  trá»£ lÃ½ áº£o AI xuáº¥t sáº¯c cá»§a há»‡ thá»‘ng E-commerce.
    QUY Táº®C Báº®T BUá»˜C:
    1. ThÃ´ng tin trong [NGá»® Cáº¢NH Sáº¢N PHáº¨M] lÃ  cÃ¡c sáº£n pháº©m ÄÃƒ ÄÆ¯á»¢C Há»† THá»NG Lá»ŒC CHUáº¨N XÃC theo má»©c giÃ¡ vÃ  danh má»¥c khÃ¡c yÃªu cáº§u.
    2. HÃ£y Tá»° TIN giá»›i thiá»‡u cÃ¡c sáº£n pháº©m nÃ y. TUYá»†T Äá»I KHÃ”NG Ä‘Æ°á»£c nÃ³i lÃ  "khÃ´ng cÃ³ sáº£n pháº©m nÃ o phÃ¹ há»£p" náº¿u trong ngá»¯ cáº£nh cÃ³ chá»©a sáº£n pháº©m.
    3. KHÃ”NG tá»± Ã½ so sÃ¡nh toÃ¡n há»c (lá»›n hÆ¡n, nhá» hÆ¡n). Chá»‰ trÃ¬nh bÃ y láº¡i tÃªn, mÃ´ táº£ vÃ  giÃ¡ tiá»n cá»§a sáº£n pháº©m. Náº¿u cÃ³ nhiá»u sáº£n pháº©m trong ngá»¯ cáº£nh má»™t cÃ¡ch thÃ¢n thiá»‡n.
    4. Náº¿u [NGá»® Cáº¢NH Sáº¢N PHáº¨M] hoÃ n toÃ n trá»‘ng, lÃºc Ä‘Ã³ má»›i lá»‹ch sá»± xin lá»—i khÃ¡ch hÃ ng.

    [NGá»® Cáº¢NH Sáº¢N PHáº¨M]:
    {context_data}
    """

      # BÆ°á»›c 3: Gá»i API OpenAI vá»›i cháº¿ Ä‘á»™ Streaming
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt.format(context_data=context)},
                {"role": "user", "content": query}
            ],
            stream=True,
            temperature=0.1 # Äá»ƒ siÃªu tháº¥p (0.1) Ä‘á»ƒ AI bÃ¡m sÃ¡t dá»¯ liá»‡u, khÃ´ng sÃ¡ng táº¡o lung tung
        )

        # Tráº£ vá» tá»«ng chá»¯ ngay khi OpenAI pháº£n há»“i
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"âŒ Lá»—i khi gá»i OpenAI API: {e}")
        yield "Há»‡ thá»‘ng AI Ä‘ang quÃ¡ táº£i, vui lÃ²ng thá»­ láº¡i sau giÃ¢y lÃ¡t."
