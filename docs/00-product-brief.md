# 00. Product Brief

## Mục tiêu

Định nghĩa sản phẩm, người dùng, giá trị và ranh giới của hệ thống trước khi triển khai.

## 1. Executive summary

**Vietnamese Traffic Law Hybrid GraphRAG** là hệ thống hỏi đáp và tra cứu pháp luật giao thông đường bộ Việt Nam. Hệ thống nhận câu hỏi tự nhiên như “Đi xe máy vượt đèn đỏ bị phạt bao nhiêu?” hoặc “Quy định này hiện còn hiệu lực không?”, sau đó:

1. chuẩn hóa câu hỏi;
2. lọc theo domain, loại phương tiện, loại văn bản và thời điểm áp dụng;
3. tìm kiếm bằng keyword và semantic retrieval;
4. hợp nhất kết quả và rerank;
5. mở rộng ngữ cảnh theo cấu trúc điều/khoản/điểm và quan hệ sửa đổi;
6. kiểm tra citation và hiệu lực;
7. sinh câu trả lời ngắn gọn, có căn cứ và có khả năng từ chối khi thiếu bằng chứng.

Sản phẩm ưu tiên **độ tin cậy của retrieval và citation** hơn việc tạo câu trả lời dài. Đây là một sản phẩm AI Engineer hoàn chỉnh trong phạm vi domain hẹp, không phải chatbot tổng quát và không tuyên bố là hệ thống tư vấn pháp lý.

## 2. Product statement

> Giúp người dân, sinh viên và nhân sự vận hành giao thông tìm đúng quy định pháp luật giao thông Việt Nam và hiểu căn cứ pháp lý hiện hành mà không phải đọc thủ công nhiều văn bản liên quan.

## 3. Target users

| Persona | Nhu cầu | Rủi ro cần kiểm soát |
|---|---|---|
| Người dân/người lái xe | Hỏi nhanh về lỗi, giấy tờ, mức phạt, điều kiện tham gia giao thông | Hiểu nhầm câu trả lời là tư vấn pháp lý cuối cùng |
| Sinh viên/người học luật | Tra cứu điều khoản, so sánh văn bản và phiên bản | Citation thiếu hoặc dùng văn bản cũ |
| Nhân sự vận tải/doanh nghiệp nhỏ | Tìm quy định vận tải, phương tiện, trách nhiệm | Bỏ sót văn bản liên quan |
| Người đánh giá hệ thống | Kiểm tra retrieval, citation, latency và cập nhật dữ liệu | Metric đẹp nhưng không phản ánh tính đúng pháp lý |

## 4. Core value proposition

- **Có căn cứ:** mỗi câu trả lời gắn với document/article/clause/point cụ thể.
- **Có thời điểm:** người dùng có thể hỏi theo ngày hoặc xem trạng thái hiện tại.
- **Hiểu cấu trúc pháp luật:** hệ thống biết một điểm thuộc khoản và điều nào.
- **Tìm kiếm lai:** keyword bắt số hiệu/điều khoản; dense retrieval bắt cách diễn đạt tự nhiên.
- **Minh bạch:** hiển thị nguồn, score/quality signal và lý do abstain khi có.
- **Có thể đánh giá:** mọi tầng từ parser đến answer đều có metric riêng.

## 5. Product boundaries

### In scope

- Pháp luật giao thông đường bộ Việt Nam.
- Văn bản quy phạm pháp luật và văn bản liên quan trực tiếp đến giao thông trong data manifest.
- Hỏi đáp một lượt và hội thoại ngắn có rewrite câu hỏi.
- Tra cứu điều/khoản/điểm.
- So sánh hiệu lực, sửa đổi, thay thế, bãi bỏ trong phạm vi quan hệ đã được xác minh.
- Hiển thị citation và link nguồn.
- Offline ingestion có version, retry, validation và re-index.
- Evaluation dataset và dashboard/log cơ bản.

### Out of scope

- Tư vấn pháp lý chính thức hoặc kết luận trách nhiệm pháp lý.
- Toàn bộ pháp luật Việt Nam.
- Phán đoán kết quả tranh chấp, kiện tụng hoặc xử lý hồ sơ cá nhân.
- Nhận diện biển báo từ camera trong v1.
- Tự động nộp phạt, khiếu nại hoặc thực hiện hành động pháp lý.
- Fine-tuning LLM trước khi có benchmark chứng minh RAG không đủ.
- Multi-agent tự trị chỉ để làm đẹp kiến trúc.

## 6. Success definition

Sản phẩm được xem là đạt v1 khi có thể ingest một data snapshot có thể tái lập, phục vụ câu hỏi qua API/UI, trả citation hợp lệ, biết abstain trong các ca thiếu evidence và có báo cáo ablation cho retrieval. Mục tiêu chất lượng cụ thể nằm trong [07-evaluation-plan.md](07-evaluation-plan.md), không được coi là kết quả đã đạt trước khi chạy benchmark.

## 7. Assumptions

- Nguồn chính được lấy từ cổng pháp luật chính thống và lưu lại URL, timestamp, hash.
- Corpus ban đầu kế thừa khoảng 12 văn bản traffic trong repo tham khảo; trước khi đánh giá phải đóng băng thành manifest có version.
- Mục tiêu đồ án là khoảng 15–30 document/version records và tối thiểu 300 câu hỏi được kiểm tra citation; target tốt hơn là 500 câu.
- Có thể dùng LLM hosted cho generation trong môi trường demo; embedding/reranker nên benchmark được bằng model local.
- Một người hoặc nhóm nhỏ vận hành, nên ưu tiên ít service và pipeline dễ debug.

## 8. Failure modes chính

- Trả lời đúng ngôn ngữ nhưng sai điều luật.
- Trích dẫn tồn tại nhưng không hỗ trợ claim.
- Dùng văn bản đã bị thay thế.
- Retrieval không lấy được điều đúng nên reranker không thể sửa.
- Parser làm mất cấu trúc hoặc nhầm số điều.
- LLM bị prompt injection qua nội dung văn bản hoặc câu hỏi.
- LLM/API timeout hoặc trả output sai schema.
- Dữ liệu nguồn thay đổi nhưng index vẫn cũ.

## 9. Acceptance criteria

- Người dùng hỏi được bằng tiếng Việt và nhận câu trả lời có nguồn.
- Mỗi source có mã văn bản, điều/khoản/điểm và URL hoặc định danh data snapshot.
- Hệ thống phân biệt được `current`, `repealed`, `amended`, `unknown`.
- Có câu trả lời abstain khi không có evidence đạt ngưỡng.
- Có thể tái lập index từ raw data bằng một lệnh/job.
- Có test/metric cho parser, retrieval, citation và API contract.
