"""The fixed category taxonomy, shared by product input and query-filter inference.

Kept in one place so a product can never be stored with a category the chat
filter is incapable of matching (see app/services/rag_service.py analyze_query).
"""

from typing import Literal

Category = Literal["dien_tu", "thoi_trang"]
