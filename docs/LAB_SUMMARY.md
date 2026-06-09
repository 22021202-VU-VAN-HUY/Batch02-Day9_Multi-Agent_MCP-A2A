# Tổng Kết Lab Multi-Agent Và A2A

## Các Phần Đã Hoàn Thành

- Stage 1: đổi câu hỏi Direct LLM và cấu hình `temperature=0.3`.
- Stage 2: thêm knowledge base luật lao động và tool kiểm tra thời hiệu.
- Stage 3: thêm tool `search_case_law` cho ReAct Agent.
- Stage 4: thêm `privacy_agent`, conditional routing và sơ đồ kiến trúc.
- Stage 5: trace request, kiểm tra lỗi khi Tax Agent dừng và chỉnh prompt Tax Agent.

Báo cáo chi tiết Stage 5: [STAGE5_LAB.md](STAGE5_LAB.md).

## Câu Hỏi Ôn Tập

### 1. Khi nào nên dùng Single Agent thay vì Multi-Agent?

Nên dùng Single Agent khi bài toán thuộc một domain rõ ràng, có ít tool, quy
trình xử lý đơn giản và không cần thực hiện nhiều tác vụ song song. Cách này
giúp hệ thống dễ triển khai, dễ debug, phản hồi nhanh và ít tốn chi phí API hơn.

Ví dụ: một agent chỉ tra cứu luật lao động hoặc tính mức phạt có thể xử lý tốt
mà không cần chia thành nhiều agent.

Nên dùng Multi-Agent khi bài toán cần nhiều chuyên môn độc lập như luật hợp
đồng, thuế, tuân thủ và quyền riêng tư; hoặc khi các tác vụ có thể chạy song
song để giảm thời gian xử lý.

### 2. A2A có ưu điểm gì so với REST hoặc gRPC thông thường?

REST và gRPC là cơ chế giao tiếp tổng quát, trong khi A2A bổ sung các khái niệm
dành riêng cho agent:

- `Agent Card` mô tả danh tính, endpoint và khả năng của agent.
- Cấu trúc chuẩn cho `Message`, `Task`, `Part` và `Artifact`.
- Discovery dựa trên capability hoặc loại task.
- `context_id` liên kết các task trong cùng một hội thoại.
- `trace_id` hỗ trợ theo dõi request qua nhiều agent.
- Agent viết bằng framework hoặc nhà cung cấp khác nhau có thể giao tiếp theo
  cùng một chuẩn.

A2A không thay thế HTTP. Nó định nghĩa giao thức và cấu trúc dữ liệu ở tầng ứng
dụng phía trên HTTP.

### 3. Làm thế nào để ngăn Infinite Delegation Loop trong A2A?

Có thể kết hợp các biện pháp sau:

- Giới hạn độ sâu bằng `MAX_DELEGATION_DEPTH`.
- Tăng `delegation_depth` sau mỗi lần chuyển request.
- Lưu danh sách agent đã đi qua để tránh quay lại agent cũ.
- Phát hiện chu trình trong delegation graph.
- Đặt timeout cho từng request và toàn bộ workflow.
- Giới hạn số lần retry và tổng số hop.
- Chỉ cho phép agent gọi các task hoặc agent được cấp quyền.

Project hiện dùng:

```python
MAX_DELEGATION_DEPTH = 3
```

Khi đạt giới hạn, Law Agent ngừng gọi thêm specialist agent và chuyển sang tổng
hợp những kết quả đang có.

### 4. Tại sao cần Registry? Có thể Hardcode URL không?

Registry cho phép agent tự đăng ký endpoint và capability khi khởi động. Agent
khác có thể tìm service theo task như `legal_question`, `tax_question` hoặc
`compliance_question`.

Ưu điểm của Registry:

- Không phải sửa code phía gọi khi endpoint thay đổi.
- Giảm liên kết trực tiếp giữa các agent.
- Có thể mở rộng để hỗ trợ nhiều instance và load balancing.
- Có thể bổ sung health check, heartbeat và tự động loại bỏ endpoint lỗi.

Có thể hardcode URL trong demo nhỏ, nhưng cách này khó bảo trì, khó scale và
phải sửa code khi host hoặc port thay đổi.

Registry hiện tại lưu dữ liệu trong memory và chưa có health check. Vì vậy khi
Tax Agent dừng, Registry vẫn có thể trả endpoint cũ. Trong production nên bổ
sung heartbeat, TTL hoặc health check.

## Kết Luận

Năm stage thể hiện quá trình phát triển từ gọi LLM trực tiếp đến một hệ thống
agent phân tán:

```text
Direct LLM
  -> LLM + Tools
  -> ReAct Agent
  -> Multi-Agent In-Process
  -> Distributed A2A
```

Độ phức tạp tăng dần nhưng hệ thống cũng có thêm khả năng chuyên môn hóa, xử lý
song song, discovery động và triển khai từng agent như một service độc lập.
