# Kiến Trúc Stage 4

```mermaid
flowchart TD
    START([START]) --> LAW[analyze_law<br/>Phân tích pháp lý tổng quát]
    LAW --> ROUTER{check_routing<br/>Định tuyến bằng từ khóa và Send API}

    ROUTER -->|tax / IRS / thuế| TAX[call_tax_specialist<br/>Tax ReAct agent]
    ROUTER -->|compliance / SEC / SOX / AML| COMPLIANCE[call_compliance_specialist<br/>Compliance ReAct agent]
    ROUTER -->|data / privacy / GDPR / dữ liệu| PRIVACY[privacy_agent<br/>Privacy agent]
    ROUTER -->|Không cần specialist| AGGREGATE[aggregate]

    TAX --> AGGREGATE
    COMPLIANCE --> AGGREGATE
    PRIVACY --> AGGREGATE
    AGGREGATE --> END([END])
```

## Luồng Thực Thi

1. `analyze_law` tạo phân tích pháp lý tổng quát.
2. `check_routing` kiểm tra câu hỏi và trả về một hoặc nhiều đối tượng LangGraph `Send`.
3. Tax, Compliance và Privacy Agent chạy song song khi câu hỏi chứa từ khóa tương ứng.
4. Mỗi specialist agent ghi kết quả vào một field riêng trong shared state có reducer.
5. `aggregate` kết hợp tất cả phân tích hiện có thành câu trả lời cuối cùng.

Stage 4 chạy tất cả agent trong cùng một Python process. Stage 5 giữ nguyên ý
tưởng điều phối này nhưng chuyển các agent thành những HTTP service độc lập và
giao tiếp bằng A2A protocol.
