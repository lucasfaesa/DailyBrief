"""Run: python src/test_pipeline.py — checks batch mapping, fallback, and relevance filter without network."""
import pipeline
from llm import _try_parse_json

pipeline.extract_text = lambda item, cfg: item["title"]


class FakeRouter:
    def generate_json(self, prompt):
        if "comments_summary" in prompt:
            return {"comments_summary": "c"}
        # id "b" missing from the reply → fallback; "c" trivial → dropped
        return {"items": [
            {"id": "a", "theme": "national_politics", "relevance": 5, "short_summary": "s", "summary": "long"},
            {"id": "c", "theme": "others", "relevance": 1, "short_summary": "x"},
        ]}

    def print_summary(self):
        pass


cfg = {"collection": {"batch_size": 10, "batch_text_chars": 100, "min_relevance": 2,
                      "relevance_threshold": 4, "max_high_relevance": 5}}
items = [
    {"id": "a", "title": "A", "source": "s", "category_hint": "others", "comments": ["hi"]},
    {"id": "b", "title": "B", "source": "s", "category_hint": "anime", "comments": []},
    {"id": "c", "title": "C", "source": "s", "category_hint": "others", "comments": []},
]
out = pipeline.process_items(items, cfg, FakeRouter())
assert [i["id"] for i in out] == ["a", "b"], out
a, b = out
assert a["theme"] == "national_politics" and a["article_summary"] == "long" and a["comments_summary"] == "c"
assert b["theme"] == "anime" and b["relevance"] == 2 and "article_summary" not in b
assert _try_parse_json('```json\n{"items": []}\n```') == {"items": []}
print("ok")
