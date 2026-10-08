agent: claude
model: claude-opus-5-5
---
user: README에 로컬 실행 방법 한 줄 추가해줘
call Read: README.md
result: # 주문 API
call Edit: README.md (+ 로컬 실행: `uvicorn app:app --reload`)
result: 수정 완료
assistant: README에 로컬 실행 방법을 추가했어요.
user: 고마워
