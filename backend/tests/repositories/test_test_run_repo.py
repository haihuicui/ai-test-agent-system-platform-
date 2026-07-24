"""
TestRunRepository 纯逻辑单元测试

覆盖 _aggregate_progress_from_jobs 的计数分配边界场景，
重点保证 total 始终等于各分项之和，避免前端通过率/进度条异常。
"""

from types import SimpleNamespace
from uuid import uuid4

from app.repositories.test_run_repo import _aggregate_progress_from_jobs
from app.schemas.enums import JobStatus


def _make_job(status, result_summary=None):
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        result_summary=result_summary,
    )


class TestAggregateProgressFromJobs:
    def test_explicit_counts_sum_correctly(self):
        jobs = [
            _make_job(
                JobStatus.COMPLETED,
                {"total": 10, "passed": 5, "failed": 3, "skipped": 2},
            ),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        assert result == {
            "test_cases_count": 10,
            "untested_count": 0,
            "passed_count": 5,
            "retest_count": 0,
            "failed_count": 3,
            "blocked_count": 0,
            "skipped_count": 2,
            "in_progress_count": 0,
        }

    def test_failed_job_with_explicit_counts(self):
        jobs = [
            _make_job(
                JobStatus.FAILED,
                {"total": 10, "passed": 0, "failed": 10, "skipped": 0},
            ),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 10
        assert result["passed_count"] == 0
        assert result["failed_count"] == 10

    def test_zero_counts_with_failure_category_gets_default_failed(self):
        # 主要修复点：result_summary 显式存在但 passed/failed/skipped 全为 0
        jobs = [
            _make_job(
                JobStatus.FAILED,
                {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "failure_category": "assertion",
                },
            ),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 1
        assert result["failed_count"] == 1
        assert result["passed_count"] == 0

    def test_zero_total_but_nonzero_failed_expands_total(self):
        jobs = [
            _make_job(
                JobStatus.FAILED,
                {"total": 0, "passed": 0, "failed": 5, "skipped": 0},
            ),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 5
        assert result["failed_count"] == 5
        assert result["passed_count"] == 0

    def test_completed_without_counts_defaults_to_passed(self):
        jobs = [_make_job(JobStatus.COMPLETED, None)]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 1
        assert result["passed_count"] == 1
        assert result["failed_count"] == 0

    def test_failed_without_counts_defaults_to_failed(self):
        jobs = [_make_job(JobStatus.FAILED, None)]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 1
        assert result["failed_count"] == 1
        assert result["passed_count"] == 0

    def test_running_counts_as_in_progress(self):
        jobs = [_make_job(JobStatus.RUNNING, None)]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 1
        assert result["in_progress_count"] == 1

    def test_pending_counts_as_untested(self):
        jobs = [_make_job(JobStatus.PENDING, None)]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 1
        assert result["untested_count"] == 1

    def test_mixed_jobs_aggregate_correctly(self):
        jobs = [
            _make_job(
                JobStatus.COMPLETED,
                {"total": 5, "passed": 5, "failed": 0, "skipped": 0},
            ),
            _make_job(
                JobStatus.FAILED,
                {"total": 5, "passed": 2, "failed": 3, "skipped": 0},
            ),
            _make_job(JobStatus.RUNNING, None),
            _make_job(JobStatus.PENDING, None),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 12
        assert result["passed_count"] == 7
        assert result["failed_count"] == 3
        assert result["in_progress_count"] == 1
        assert result["untested_count"] == 1

    def test_total_greater_than_accounted_fills_gap_for_completed(self):
        jobs = [
            _make_job(
                JobStatus.COMPLETED,
                {"total": 10, "passed": 5, "failed": 3, "skipped": 1},
            ),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        # accounted=9 < total=10, 差额 1 按状态补齐到 passed
        assert result["passed_count"] == 6
        assert result["failed_count"] == 3
        assert result["skipped_count"] == 1
        assert result["test_cases_count"] == 10

    def test_total_greater_than_accounted_fills_gap_for_failed(self):
        """失败作业中未执行的部分应计为 skipped，而非 failed。

        场景：3 步骤场景，步骤 2 失败后 continue_on_failure=false，
        步骤 3 从未执行。此时 total=3, passed=1, failed=1, skipped=0
        (accounted=2 < total=3)，差额 1 应归入 skipped 而非 failed，
        避免前端展示"失败数虚高"。
        """
        jobs = [
            _make_job(
                JobStatus.FAILED,
                {"total": 10, "passed": 5, "failed": 3, "skipped": 1},
            ),
        ]
        result = _aggregate_progress_from_jobs(jobs)
        # accounted=9 < total=10, 差额 1 按状态补齐到 skipped
        assert result["passed_count"] == 5
        assert result["failed_count"] == 3
        assert result["skipped_count"] == 2
        assert result["test_cases_count"] == 10

    def test_only_failure_category_no_counts_defaults_by_status(self):
        # 仅有 failure_category 等元数据，没有计数字段 → 按状态兜底
        jobs = [_make_job(JobStatus.FAILED, {"failure_category": "assertion"})]
        result = _aggregate_progress_from_jobs(jobs)
        assert result["test_cases_count"] == 1
        assert result["failed_count"] == 1
        assert result["passed_count"] == 0

    def test_result_sums_match_total(self):
        """所有边界场景都必须满足 total 等于各分项之和。"""
        scenarios = [
            [_make_job(JobStatus.COMPLETED, {"total": 10, "passed": 5, "failed": 3, "skipped": 2})],
            [_make_job(JobStatus.FAILED, {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "failure_category": "infra"})],
            [_make_job(JobStatus.FAILED, {"total": 0, "passed": 0, "failed": 5, "skipped": 0})],
            [_make_job(JobStatus.COMPLETED, None)],
            [_make_job(JobStatus.FAILED, None)],
            [_make_job(JobStatus.RUNNING, None)],
            [_make_job(JobStatus.PENDING, None)],
        ]
        for jobs in scenarios:
            result = _aggregate_progress_from_jobs(jobs)
            accounted = (
                result["passed_count"]
                + result["failed_count"]
                + result["skipped_count"]
                + result["blocked_count"]
                + result["in_progress_count"]
                + result["untested_count"]
                + result["retest_count"]
            )
            assert accounted == result["test_cases_count"], (
                f"total={result['test_cases_count']} != accounted={accounted} for jobs={jobs}"
            )
