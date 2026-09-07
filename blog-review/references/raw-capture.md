# raw 캡처 — 교정 전 사고의 원문 보존

raw는 대화 백업이 아니라 **교정 전 사고의 원문 데이터**다. 나중에 "나는 처음에 이걸 어떻게 봤나"를 다시 읽기 위한 것이라, **고치면 가치가 사라진다.**

## 언제 쓰나

**질문에 답하는 중에는 파일을 쓰거나 스크립트를 실행하지 않는다.** 5단계에서 노트를 저장할 때 한 번에 처리한다.

## 무엇을 담나

- **수집 경계:** 블로그 URL을 받은 시점부터 해당 리뷰를 처음 저장·푸시하는 시점까지.
- **포함:** 사용자가 직접 보낸 URL, 이해, 생각, 질문, **사고 내용에 영향을 주는 요청**. 성격이 여럿이면 `kinds`에 여러 값.
- **제외:** 에이전트 답변, 도구 출력, 원문 글 본문, 최종 노트에서 새로 생성한 문장, **저장·정리·커밋 등 진행만 지시하는 행정적 요청**.
- **원문 불변:** `text`의 맞춤법·띄어쓰기·줄바꿈·표현을 요약하거나 고치지 않는다. 오타도 그대로 둔다.
- **예외:** 자격증명·토큰·비밀키와 사용자가 비공개로 지정한 문구만 `[REDACTED: 유형]`으로 치환하고, `redacted: true`와 `redaction_types`를 남긴다.
- **소급 금지:** 기존 리뷰의 원문을 재구성하지 않는다.

허용 `kinds`: `source` · `understanding` · `thought` · `question` · `request`

## 저장 순서

1. 노트 frontmatter에 `raw: ../raw/<review-id>.jsonl`을 넣고 **노트 파일을 먼저** 만든다.
2. 대화에서 사용자 입력만 순서대로 모아 임시 manifest JSON으로 쓴다.
3. 스크립트를 실행한다.
   ```bash
   python3 <이 스킬 폴더>/scripts/write_raw.py \
     --review reviews/<review-id>.md \
     --input  /tmp/blog-review-raw-<review-id>.json \
     --output raw/<review-id>.jsonl
   ```
4. 비밀정보 후보가 걸리면 **원문을 지우지 말고** 해당 값만 `[REDACTED: credential]`로 바꾸고 메타데이터를 설정한 뒤 재실행한다.
5. 성공·실패와 관계없이 임시 manifest를 지우고, 생성된 JSONL과 노트를 같은 커밋에 포함한다.

## manifest 형식

```json
{
  "review_id": "2026-08-14-company-topic",
  "entries": [
    {
      "kinds": ["understanding", "question"],
      "text": "사용자가 실제로 입력한 원문",
      "redacted": false
    }
  ]
}
```

`schema_version: 1`과 1부터 시작하는 `sequence`는 스크립트가 부여한다.

## 스크립트가 막아주는 것

`scripts/write_raw.py`는 stdlib만 쓰고 의존성이 없다. 다음을 검증한다.

- `review_id`가 `YYYY-MM-DD-케밥` 형식인지
- 노트 파일명과 `review_id`가 일치하는지
- 노트 frontmatter에 `raw:` 경로가 **정확히** 적혀 있는지
- 출력이 `raw/<review-id>.jsonl` 인지, **이미 있으면 덮어쓰기 거부**
- `kinds`가 허용 값인지, 중복이 없는지
- 개인키 · AWS 액세스 키 · GitHub 토큰 · `sk-` 형태 키 · `password=` 류 패턴
- redaction 메타데이터의 정합성

원자적으로 쓴다 — 임시 파일에 쓰고, 왕복 파싱으로 검증한 뒤, 하드링크로 발행한다. 중간에 실패해도 반쪽짜리 JSONL이 남지 않는다.

## 다시 읽을 때

JSONL 한 줄 = 입력 하나다.

```bash
# 안 닫힌 질문만 모아보기
grep -h '"question"' raw/*.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    print('-', json.loads(line)['text'][:120])
"
```
