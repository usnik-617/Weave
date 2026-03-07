from __future__ import annotations


_TEMPLATE_LABELS = {
    "notice": "공지 템플릿",
    "review": "활동 후기 템플릿",
    "minutes": "회의록 템플릿",
}


def list_template_items():
    return [{"type": key, "label": label} for key, label in _TEMPLATE_LABELS.items()]


def default_template_title(raw_title):
    title = str(raw_title or "").strip()
    return title or "제목"


def build_template_content(template_type, title):
    templates = {
        "notice": f"[공지] {title}\n\n1) 일정\n2) 장소\n3) 준비물\n4) 유의사항",
        "review": f"[활동후기] {title}\n\n- 활동 개요\n- 참여 소감\n- 다음 개선점",
        "minutes": f"[회의록] {title}\n\n- 참석자\n- 회의 안건\n- 결정 사항\n- 액션 아이템",
    }
    return templates.get(str(template_type or "").strip().lower())
