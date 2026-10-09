#!/usr/bin/env python3
"""codex CLI의 로컬 모델 캐시를 한 줄에 하나씩 덤프한다.

    python3 -I scripts/codex-models.py

캐시는 codex가 시작할 때 서버에서 받아 두는 것이라 공식 문서보다 정확하다.
모델별 추론 단계·기본값·service tier·선택기 노출 여부가 들어 있다.
"""
import json
import sys
from pathlib import Path

CACHE = Path.home() / ".codex" / "models_cache.json"

if not CACHE.exists():
    sys.exit(f"{CACHE} 없음 — codex를 한 번 실행하면 생긴다")

data = json.loads(CACHE.read_text())
print(f"fetched_at: {data.get('fetched_at')}\n")

for m in data["models"]:
    levels = [l["effort"] for l in m.get("supported_reasoning_levels", [])]
    tiers = [t["id"] for t in m.get("service_tiers", [])]
    print(
        f"{m['slug']:<18} vis={m.get('visibility', '?'):<4} "
        f"default={m.get('default_reasoning_level', '?'):<6} "
        f"levels={','.join(levels)} tiers={','.join(tiers) or '-'}"
    )
    print(f"{'':<18} {m.get('description', '')}")
