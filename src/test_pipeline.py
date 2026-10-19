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


class DedupRouter:
    def generate_json(self, prompt):
        return {"groups": [["x", "y", "ghost"], "junk"]}


dups = [{"id": "x", "title": "EN", "theme": "economy", "short_summary": "s", "relevance": 3},
        {"id": "y", "title": "PT", "theme": "economy", "short_summary": "s", "relevance": 4},
        {"id": "z", "title": "Z", "theme": "economy", "short_summary": "s", "relevance": 3}]
assert [i["id"] for i in pipeline._drop_duplicates(dups, DedupRouter())] == ["y", "z"]
assert _try_parse_json('```json\n{"items": []}\n```') == {"items": []}
print("ok")

# Router: a 503 must not disable the provider for later requests; a fatal error must.
import llm
llm.time.sleep = lambda s: None


class Flaky:
    def __init__(self, name, errors):
        self.name, self.errors = name, errors

    def generate(self, prompt):
        if self.errors:
            raise self.errors.pop(0)
        return '{"ok": 1}'


r = llm.LLMRouter.__new__(llm.LLMRouter)
r.cfg = {"rate_limit_pause_seconds": 0, "max_retries_per_provider": 2, "backoff_base_seconds": 2, "json_fix_retries": 0}
r.stats, r._exhausted = llm.LLMStats(), set()
busy = llm.ProviderError(503, "high demand")
r._providers = [Flaky("a", [busy, busy]), Flaky("b", [llm.ProviderError(404, "gone")])]
assert r.generate_json("x") is None  # a: 503 twice, b: fatal
assert r._exhausted == {"b"}
assert r.generate_json("x") == {"ok": 1}  # a recovered
print("router ok")
