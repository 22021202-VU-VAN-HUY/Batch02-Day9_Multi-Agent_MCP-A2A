"""Bài Tập 2: Thêm Tools và Knowledge Base

Hoàn thành các TODO để thêm tool và knowledge base entry mới.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# Knowledge base
LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages; (2) consequential damages; (3) specific performance; "
            "(4) cover damages. Statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "labor_law",
        "keywords": [
            "lao động",
            "sa thải",
            "hợp đồng lao động",
            "labor",
            "termination",
        ],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019, người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp: (1) người lao động "
            "thường xuyên không hoàn thành công việc; (2) bị ốm đau, tai nạn đã điều trị "
            "12 tháng chưa khỏi; (3) thiên tai, hỏa hoạn; (4) người lao động đủ tuổi nghỉ hưu."
        ),
    },
]


@tool
def search_legal_knowledge(query: str) -> str:
    """Tìm kiếm trong knowledge base pháp lý."""
    query_lower = query.lower()
    for entry in LEGAL_KNOWLEDGE:
        if any(kw in query_lower for kw in entry["keywords"]):
            return f"[{entry['id']}] {entry['text']}"
    return "Không tìm thấy thông tin liên quan."


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án.

    Args:
        case_type: Loại vụ án (contract, tort, property).
    """
    limits = {
        "contract": "4 năm (UCC § 2-725)",
        "tort": "2-3 năm tùy bang",
        "property": "5 năm",
    }
    return limits.get(case_type.lower(), "Không xác định")


async def main():
    load_dotenv()
    llm = get_llm()
    
    tools = [search_legal_knowledge, check_statute_of_limitations]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {registered_tool.name: registered_tool for registered_tool in tools}
    
    question = "Thời hiệu khởi kiện vụ vi phạm hợp đồng là bao lâu?"
    
    messages = [
        SystemMessage(content="Bạn là chuyên gia pháp lý. Sử dụng tools để tra cứu thông tin."),
        HumanMessage(content=question),
    ]
    
    print(f"Câu hỏi: {question}\n")
    
    # First LLM call - decide which tools to use
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)
    
    # Execute tools if requested
    if response.tool_calls:
        tool_results = []
        for tool_call in response.tool_calls:
            print(f"🔧 Gọi tool: {tool_call['name']}")
            selected_tool = tool_map.get(tool_call["name"])
            if selected_tool is None:
                tool_result = f"Không tìm thấy tool: {tool_call['name']}"
            else:
                tool_result = selected_tool.invoke(tool_call["args"])

            tool_results.append(tool_result)
            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
        
        # Use a fresh synthesis prompt for compatibility with providers that do
        # not reliably accept tool-call history in a follow-up request.
        synthesis_messages = [
            SystemMessage(
                content=(
                    "Bạn là chuyên gia pháp lý. Hãy trả lời ngắn gọn bằng tiếng Việt, "
                    "chỉ dựa trên kết quả tool được cung cấp."
                )
            ),
            HumanMessage(
                content=(
                    f"Câu hỏi: {question}\n\n"
                    f"Kết quả tool:\n{'\n\n'.join(tool_results)}"
                )
            ),
        ]
        final_response = await llm.ainvoke(synthesis_messages)
        final_text = final_response.content.strip() or "\n\n".join(tool_results)
        print(f"\n✅ Kết quả:\n{final_text}")
    else:
        print(f"\n✅ Kết quả:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
