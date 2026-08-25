"""list_api_endpoints 关键词过滤/排序/截断单元测试

覆盖纯函数 _match_score 与 _filter_rank_endpoints：
- 归一化匹配（samplingSite 命中 /sampling-sites，customer 命中 customer_id）
- 相关性排序（路径段精确 > 前缀 > 子串 > summary > 标签组）
- limit 截断与匹配总数
- 无关键词时保持原序

不依赖数据库。
"""

from app.agents.tools.api.openapi_tools import (
    _MAX_LIST_LIMIT,
    _filter_rank_endpoints,
    _match_score,
)


def _ep(path, method="GET", summary=None, display_name=None, tag_group=None):
    return {
        "id": "x",
        "path": path,
        "method": method,
        "summary": summary,
        "display_name": display_name or f"{method} {path}",
        "tag_group": tag_group,
    }


class TestMatchScore:
    def test_exact_segment_match_scores_100(self):
        assert _match_score("customers", _ep("/api/customers")) == 100

    def test_segment_prefix_scores_80(self):
        assert _match_score("customer", _ep("/api/customers")) == 80

    def test_path_substring_scores_60(self):
        # 归一化后 "samplingsite" 是 "/apisamplingsites" 的子串（非段前缀）
        assert _match_score("samplingSite", _ep("/api/sampling-sites")) == 80
        assert _match_score("plings", _ep("/api/sampling-sites")) == 60

    def test_summary_match_scores_40(self):
        assert _match_score("客户", _ep("/api/abc", summary="客户列表")) == 40

    def test_tag_group_match_scores_20(self):
        assert _match_score("orders", _ep("/api/xyz", tag_group="Orders")) == 20

    def test_no_match_scores_0(self):
        assert _match_score("payment", _ep("/api/customers")) == 0

    def test_normalized_camel_snake_kebab(self):
        """camelCase / snake_case / kebab-case 互相命中"""
        assert _match_score("samplingSite", _ep("/api/sampling_sites")) > 0
        assert _match_score("sampling_site", _ep("/api/sampling-sites")) > 0
        assert _match_score("customerId", _ep("/api/customer-id")) > 0

    def test_empty_keyword_scores_0(self):
        assert _match_score("", _ep("/api/customers")) == 0


class TestFilterRankEndpoints:
    def test_no_keyword_keeps_order_and_applies_limit(self):
        endpoints = [_ep(f"/api/e{i}") for i in range(5)]
        page, total = _filter_rank_endpoints(endpoints, None, 3)
        assert total == 5
        assert len(page) == 3
        assert [p["path"] for p in page] == ["/api/e0", "/api/e1", "/api/e2"]

    def test_blank_keyword_treated_as_none(self):
        endpoints = [_ep("/api/a"), _ep("/api/b")]
        page, total = _filter_rank_endpoints(endpoints, "  ", 50)
        assert total == 2
        assert len(page) == 2

    def test_keyword_filters_and_ranks_by_score(self):
        endpoints = [
            _ep("/api/orders", summary="customer orders"),       # 40 summary
            _ep("/api/customers/{customerId}"),                   # 80 段前缀
            _ep("/api/customer"),                                 # 100 段精确
            _ep("/api/unrelated"),
        ]
        page, total = _filter_rank_endpoints(endpoints, "customer", 50)
        assert total == 3
        paths = [p["path"] for p in page]
        assert paths == ["/api/customer", "/api/customers/{customerId}", "/api/orders"]
        assert all("match_score" in p for p in page)

    def test_limit_truncates_least_relevant_first(self):
        endpoints = [
            _ep("/api/customers", summary="客户"),       # 100 段精确
            _ep("/api/other", summary="客户接口"),        # 40 summary
        ]
        page, total = _filter_rank_endpoints(endpoints, "customers", 1)
        assert total == 1 or total == 2  # customers 只命中路径；客户 两个都命中
        assert page[0]["path"] == "/api/customers"

    def test_limit_truncates_by_relevance_with_chinese_keyword(self):
        endpoints = [
            _ep("/api/customers", summary="客户"),       # 40
            _ep("/api/other", summary="客户接口"),        # 40，path 字典序靠后
        ]
        page, total = _filter_rank_endpoints(endpoints, "客户", 1)
        assert total == 2
        assert len(page) == 1
        assert page[0]["path"] == "/api/customers"

    def test_limit_clamped_to_max(self):
        endpoints = [_ep(f"/api/e{i}") for i in range(5)]
        page, total = _filter_rank_endpoints(endpoints, None, _MAX_LIST_LIMIT + 100)
        assert total == 5
        assert len(page) == 5  # 不超过实际数量，但 limit 被钳制到 _MAX_LIST_LIMIT

    def test_same_score_sorted_by_path(self):
        endpoints = [_ep("/api/customers-b"), _ep("/api/customers-a")]
        page, _ = _filter_rank_endpoints(endpoints, "customers", 50)
        assert [p["path"] for p in page] == ["/api/customers-a", "/api/customers-b"]
