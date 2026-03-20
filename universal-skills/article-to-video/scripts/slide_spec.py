"""
slide-spec helpers.

The structured slide-spec document is the source of truth for rendering. It can
be produced from outline.json or written directly by users for tighter control.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy

DEFAULT_RENDER = {
    "width": 1920,
    "height": 1080,
    "footer_safe_height": 156,
    "margin_x": 104,
    "margin_top": 90,
}

DEFAULT_THEME = {
    "style": "editorial-paper",
    "palette": {
        "paper": "#f4efe6",
        "paperStrong": "#ebe1d3",
        "ink": "#181512",
        "muted": "#5c544d",
        "accent": "#8f2d1f",
        "line": "#d8c9b8",
    },
    "font": {
        "heading": "Microsoft YaHei UI",
        "body": "Microsoft YaHei UI",
        "label": "Bahnschrift",
    },
}


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[。！？!?])\s*", text or "")
    sentences = [normalize_space(item) for item in raw if normalize_space(item)]
    return sentences


def split_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    for sentence in re.split(r"[。！？!?；;\n]", text or ""):
        for chunk in re.split(r"[，、]", sentence):
            normalized = normalize_space(chunk)
            if normalized:
                fragments.append(normalized)
    return fragments


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (text or "").lower())


def extract_keywords(text: str) -> set[str]:
    normalized = normalize_space(text)
    keywords: set[str] = set()

    for token in re.findall(r"[a-z0-9][a-z0-9+._-]*", normalized.lower()):
        if len(token) >= 2:
            keywords.add(token)

    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        if len(chunk) <= 4:
            keywords.add(chunk)
            continue
        for size in (2, 3, 4):
            for index in range(0, len(chunk) - size + 1):
                keywords.add(chunk[index:index + size])

    lowered = normalized.lower()
    alias_groups = {
        "trade-off": {"取舍", "历史", "改过什么", "踩过哪些坑"},
        "上下文": {"会话记忆", "记住", "改过什么", "长期"},
        "提醒": {"到点提醒", "记录", "临时灵感"},
        "验收": {"做验收", "需求校验", "验收"},
        "日报": {"每天", "日报"},
        "周报": {"每周", "周报"},
        "启动团队": {"启动", "需求驱动"},
    }
    for trigger, aliases in alias_groups.items():
        if trigger in lowered or trigger in normalized:
            keywords.update(aliases)

    return keywords


def text_blob(slide: dict) -> str:
    parts = [
        slide.get("slide_id", ""),
        slide.get("chapter_id", ""),
        slide.get("heading", ""),
        slide.get("summary", ""),
        slide.get("script", ""),
        " ".join(slide.get("bullets", [])),
    ]
    return " ".join(normalize_space(part) for part in parts if normalize_space(part))


def contains_any(text: str, terms: list[str]) -> bool:
    haystack = normalize_space(text).lower()
    return any(term.lower() in haystack for term in terms)


def chapter_label(chapter_id: str | None, index: int) -> str:
    if chapter_id:
        return chapter_id.replace("-", " ").replace("_", " ").upper()
    return f"PAGE {index + 1:02d}"


def footer_left_text(page: dict) -> str:
    chapter_id = page.get("chapter_id") or "page"
    slide_id = page.get("slide_id") or f"slide-{page.get('page', 0):03d}"
    left = f"{chapter_id.replace('-', ' ').upper()} / {slide_id.replace('-', ' ').upper()}"
    return left[:52]


def derive_summary(slide: dict) -> str:
    if normalize_space(slide.get("summary", "")):
        return normalize_space(slide["summary"])
    sentences = split_sentences(slide.get("script", ""))
    if sentences:
        return sentences[0]
    bullets = [normalize_space(item) for item in slide.get("bullets", []) if normalize_space(item)]
    return " / ".join(bullets[:2])


def is_process_flow_slide(slide: dict) -> bool:
    bullets = [item for item in slide.get("bullets", []) if normalize_space(item)]
    if len(bullets) < 3:
        return False

    heading_blob = " ".join(
        [
            slide.get("heading", ""),
            slide.get("slide_id", ""),
            slide.get("chapter_id", ""),
        ]
    )
    slide_blob = text_blob(slide)

    if contains_any(heading_blob, ["导向", "workflow", "流程", "路径", "阶段", "自动化"]):
        return True
    if slide.get("chapter_id") == "workflow" and contains_any(
        slide_blob,
        ["需求校验", "自动验收", "最终拍板", "执行者", "启动团队"],
    ):
        return True
    return False


def is_pillars_slide(slide: dict) -> bool:
    bullets = [item for item in slide.get("bullets", []) if normalize_space(item)]
    if len(bullets) != 3:
        return False

    heading_blob = " ".join(
        [
            slide.get("heading", ""),
            slide.get("slide_id", ""),
            slide.get("chapter_id", ""),
        ]
    )
    slide_blob = text_blob(slide)

    if contains_any(heading_blob, ["边界", "分工", "角色", "前提", "原则"]):
        return True
    if contains_any(slide_blob, ["你是谁", "你怎么做事", "你不做什么"]):
        return True
    return False


def derive_template(slide: dict, index: int, total_pages: int) -> str:
    if slide.get("template"):
        return slide["template"]
    bullets = [item for item in slide.get("bullets", []) if normalize_space(item)]
    if index == 0:
        return "cover"
    if index == total_pages - 1:
        return "closing"
    if is_process_flow_slide(slide):
        return "process-flow"
    if is_pillars_slide(slide):
        return "pillars"
    if len(bullets) >= 4:
        return "four-up"
    if len(bullets) == 3:
        return "three-up"
    return "headline-bullets"


def clean_fragment(text: str) -> str:
    cleaned = normalize_space(text)
    cleaned = re.sub(r"^(第一|第二|第三|首先|其次|最后|一方面|另一方面|然后|同时)[，,:： ]*", "", cleaned)
    return normalize_space(cleaned)


def fragment_score(fragment: str, bullet: str) -> int:
    fragment_norm = normalize_for_match(fragment)
    bullet_norm = normalize_for_match(bullet)
    if not fragment_norm or not bullet_norm:
        return 0

    score = 0
    if bullet_norm in fragment_norm:
        score += 8
    for keyword in extract_keywords(bullet):
        if keyword and keyword in fragment_norm:
            score += 3 if len(keyword) >= 3 else 1
    return score


def derive_cards(slide: dict, max_cards: int) -> list[dict]:
    bullets = [normalize_space(item) for item in slide.get("bullets", []) if normalize_space(item)]
    summary = derive_summary(slide)
    sentences = [clean_fragment(item) for item in split_sentences(slide.get("script", ""))]
    sentences = [item for item in sentences if item]
    fragments = [clean_fragment(item) for item in split_fragments(slide.get("script", ""))]
    fragments = [item for item in fragments if item]

    summary_norm = normalize_for_match(summary)
    sentence_indexes = [
        index
        for index, sentence in enumerate(sentences)
        if normalize_for_match(sentence) != summary_norm
    ]
    used_sentence_indexes: set[int] = set()
    used_indexes: set[int] = set()
    cards = []

    for index, bullet in enumerate(bullets[:max_cards]):
        best_index = -1
        best_score = -1
        for fragment_index, fragment in enumerate(fragments):
            if fragment_index in used_indexes:
                continue
            score = fragment_score(fragment, bullet)
            if normalize_for_match(fragment) == summary_norm:
                score -= 2
            if score > best_score:
                best_index = fragment_index
                best_score = score

        best_sentence_index = -1
        best_sentence_score = -1
        for sentence_rank, sentence_index in enumerate(sentence_indexes):
            if sentence_index in used_sentence_indexes:
                continue
            sentence = sentences[sentence_index]
            score = fragment_score(sentence, bullet)
            score += max(0, 2 - abs(sentence_rank - index))
            if score > best_sentence_score:
                best_sentence_index = sentence_index
                best_sentence_score = score

        body = ""
        if 0 <= best_sentence_index < len(sentences) and (
            best_sentence_score > best_score or best_score < 2 or len(fragments[best_index]) < 8
        ):
            used_sentence_indexes.add(best_sentence_index)
            body = sentences[best_sentence_index]
        elif 0 <= best_index < len(fragments):
            used_indexes.add(best_index)
            body = fragments[best_index]
        if not body:
            for sentence_index in sentence_indexes:
                if sentence_index in used_sentence_indexes:
                    continue
                used_sentence_indexes.add(sentence_index)
                body = sentences[sentence_index]
                break
        if not body and index < len(fragments):
            body = fragments[index]
        if not body:
            body = summary

        cards.append(
            {
                "title": bullet,
                "body": body,
            }
        )
    return cards


def build_slide_spec_from_outline(outline: dict) -> dict:
    render = deepcopy(DEFAULT_RENDER)
    render.update(outline.get("render", {}) if isinstance(outline.get("render"), dict) else {})

    theme = deepcopy(DEFAULT_THEME)
    theme.update(outline.get("theme", {}) if isinstance(outline.get("theme"), dict) else {})

    pages = []
    slides = outline.get("slides", [])
    for index, slide in enumerate(slides):
        template = derive_template(slide, index, len(slides))
        page_number = index + 1
        footer = {
            "left": footer_left_text(
                {
                    "chapter_id": slide.get("chapter_id"),
                    "slide_id": slide.get("slide_id"),
                    "page": page_number,
                }
            ),
            "right": f"{page_number:02d}",
            "safe_height": render["footer_safe_height"],
        }
        page = {
            "page": page_number,
            "slide_id": slide.get("slide_id") or f"slide-{page_number:03d}",
            "chapter_id": slide.get("chapter_id") or "section",
            "template": template,
            "eyebrow": slide.get("eyebrow") or chapter_label(slide.get("chapter_id"), index),
            "heading": slide.get("heading", f"Page {page_number}"),
            "summary": derive_summary(slide),
            "bullets": [normalize_space(item) for item in slide.get("bullets", []) if normalize_space(item)],
            "script": slide.get("script", ""),
            "footer": footer,
            "tts": slide.get("tts") if isinstance(slide.get("tts"), dict) else None,
        }
        if template == "cover":
            page["highlights"] = page["bullets"][:3]
        if template in {"three-up", "pillars", "closing"}:
            page["cards"] = derive_cards(slide, 3)
        if template == "four-up":
            page["cards"] = derive_cards(slide, 4)
        if template == "process-flow":
            page["steps"] = derive_cards(slide, 3)
        pages.append(page)

    return {
        "schema_version": "1.0",
        "kind": "slide-spec",
        "title": outline.get("title", ""),
        "theme": theme,
        "tts": outline.get("tts") if isinstance(outline.get("tts"), dict) else {},
        "bgm": outline.get("bgm") if isinstance(outline.get("bgm"), dict) else {},
        "render": render,
        "pages": pages,
    }


def normalize_slide_spec_document(document: dict) -> dict:
    if document.get("kind") == "slide-spec" or isinstance(document.get("pages"), list):
        spec = deepcopy(document)
    elif isinstance(document.get("slides"), list):
        spec = build_slide_spec_from_outline(document)
    else:
        raise ValueError("input JSON must be either outline.json or slide-spec.json")

    render = deepcopy(DEFAULT_RENDER)
    render.update(spec.get("render", {}) if isinstance(spec.get("render"), dict) else {})
    spec["render"] = render

    theme = deepcopy(DEFAULT_THEME)
    theme.update(spec.get("theme", {}) if isinstance(spec.get("theme"), dict) else {})
    spec["theme"] = theme

    pages = []
    raw_pages = spec.get("pages", [])
    for index, page in enumerate(raw_pages):
        page_number = page.get("page") or index + 1
        normalized = dict(page)
        normalized["page"] = page_number
        normalized["slide_id"] = page.get("slide_id") or f"slide-{page_number:03d}"
        normalized["chapter_id"] = page.get("chapter_id") or "section"
        normalized["template"] = page.get("template") or derive_template(page, index, len(raw_pages))
        normalized["eyebrow"] = page.get("eyebrow") or chapter_label(normalized["chapter_id"], index)
        normalized["heading"] = page.get("heading") or f"Page {page_number}"
        normalized["summary"] = derive_summary(page)
        normalized["bullets"] = [
            normalize_space(item) for item in page.get("bullets", []) if normalize_space(item)
        ]
        footer = page.get("footer", {}) if isinstance(page.get("footer"), dict) else {}
        normalized["footer"] = {
            "left": footer.get("left") or footer_left_text(normalized),
            "right": footer.get("right") or f"{page_number:02d}",
            "safe_height": int(footer.get("safe_height") or render["footer_safe_height"]),
        }
        if normalized["template"] in {"three-up", "pillars", "closing"} and not normalized.get("cards"):
            normalized["cards"] = derive_cards(normalized, 3)
        if normalized["template"] == "four-up" and not normalized.get("cards"):
            normalized["cards"] = derive_cards(normalized, 4)
        if normalized["template"] == "process-flow" and not normalized.get("steps"):
            normalized["steps"] = derive_cards(normalized, 3)
        pages.append(normalized)

    spec["pages"] = pages
    return spec


def load_slide_spec(path: str) -> dict:
    document = read_json(path)
    return normalize_slide_spec_document(document)


def document_label(path: str) -> str:
    return os.path.basename(path)
