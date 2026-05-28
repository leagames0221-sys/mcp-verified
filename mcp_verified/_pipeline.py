"""Audit pipeline orchestrator: glue layer between the registry, the clone,
the executors, the verdict aggregator, the budget enforcer, and the output
writer.

Implements T-15 (the orchestration half; argparse plumbing lives in
`mcp_verified.cli`).

The orchestrator is intentionally side-effect-shaped so the CLI can drive
it with simple keyword arguments. Each per-candidate run returns a
`CandidateOutcome` that the caller sums into the run-level summary line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mcp_verified.budget.per_server import (
    DEFAULT_PER_SERVER_BUDGET_SECONDS,
    BudgetResult,
    run_with_budget,
    timeout_finding,
)
from mcp_verified.checks.executors.deterministic import (
    DEFAULT_PATTERNS,
    DeterministicExecutor,
    Finding,
)
from mcp_verified.checks.executors.llm_assisted import LLMAssistedExecutor
from mcp_verified.checks.loader import CheckDefinition
from mcp_verified.clone.safe_clone import (
    ClonedRepo,
    CloneError,
    safe_clone,
)
from mcp_verified.output.assessment import write_assessment_md
from mcp_verified.output.findings import write_findings_dir
from mcp_verified.output.manifest import (
    AuditManifest,
    AuditMetadata,
    Auditor,
    Target,
    write_manifest_json,
)
from mcp_verified.output.writer import AuditDirWriter
from mcp_verified.providers.base import (
    Provider,
    ProviderError,
)
from mcp_verified.providers.mock import MockProvider
from mcp_verified.registry.client import RegistryEntry
from mcp_verified.verdict.aggregator import (
    VERDICT_UNKNOWN,
    aggregate_verdict,
    findings_summary,
)

DEFAULT_AUDITOR_NAME = "mcp-verified"
DEFAULT_AUDITOR_GITHUB = "leagames0221-sys"
DEFAULT_AUDITOR_ORG = ""

_NAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _date_yyyy_mm_dd() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _next_sequence_for(auditor: str, date: str, target_dir: Path) -> int:
    """Find the next NNN sequence under `<target>/audits/` for (auditor, date)."""
    audits_dir = target_dir / "audits"
    if not audits_dir.is_dir():
        return 1
    prefix = f"{auditor}-{date}-"
    used: set[int] = set()
    for child in audits_dir.iterdir():
        if not child.is_dir() or not child.name.startswith(prefix):
            continue
        suffix = child.name[len(prefix) :]
        if len(suffix) == 3 and suffix.isdigit():
            used.add(int(suffix))
    seq = 1
    while seq in used:
        seq += 1
    return seq


def build_audit_id(auditor: str, date: str, sequence: int) -> str:
    safe_auditor = _NAME_SAFE.sub("_", auditor) or "auditor"
    return f"{safe_auditor}-{date}-{sequence:03d}"


def _write_unknown_outcome(
    out_dir: Path,
    manifest: AuditManifest,
    findings: list[Finding],
    *,
    bucket: str,
) -> Path:
    """Write the manifest under `<out>/audits/<bucket>/<safe>/audits/<id>/`.

    Used when the target's repo_url cannot be decomposed by
    `target_host_owner_repo` (non-GitHub source, clone failure, etc.).
    """
    safe = _NAME_SAFE.sub("_", manifest.target.repo_url)[:120] or "unknown"
    audit_dir = out_dir / "audits" / bucket / safe / "audits" / manifest.audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_manifest_json(manifest, audit_dir / "audit-manifest.json")
    write_assessment_md(manifest, findings, audit_dir / "security-assessment.md")
    if findings:
        write_findings_dir(findings, audit_dir / "findings")
    return audit_dir


@dataclass(frozen=True)
class CandidateOutcome:
    """Single-candidate result; the caller sums these into a run summary."""

    entry: RegistryEntry
    verdict: str
    audit_dir: Path | None
    findings: tuple[Finding, ...]
    elapsed_seconds: float
    status: str  # "completed" | "timeout" | "unknown" | "error"


@dataclass(frozen=True)
class RunSummary:
    audited: int = 0
    verified: int = 0
    caution: int = 0
    risky: int = 0
    unknown: int = 0
    timeout: int = 0
    error: int = 0
    outcomes: tuple[CandidateOutcome, ...] = field(default_factory=tuple)

    def to_summary_line(self) -> str:
        return (
            f"audited={self.audited} "
            f"verified={self.verified} "
            f"caution={self.caution} "
            f"risky={self.risky} "
            f"unknown={self.unknown} "
            f"timeout={self.timeout} "
            f"error={self.error}"
        )


@dataclass(frozen=True)
class PipelineConfig:
    out_dir: Path
    provider: Provider = field(default_factory=MockProvider)
    checks: tuple[CheckDefinition, ...] = ()
    auditor_name: str = DEFAULT_AUDITOR_NAME
    auditor_github: str = DEFAULT_AUDITOR_GITHUB
    auditor_org: str = DEFAULT_AUDITOR_ORG
    per_server_budget_seconds: float = DEFAULT_PER_SERVER_BUDGET_SECONDS
    project_version: str = "0.0.1"


def _audit_cloned_tree(
    repo: ClonedRepo,
    *,
    provider: Provider,
    checks: tuple[CheckDefinition, ...],
) -> list[Finding]:
    deterministic = DeterministicExecutor(patterns=DEFAULT_PATTERNS).run(repo.path)
    if checks:
        llm = LLMAssistedExecutor(provider=provider).run(repo.path, list(checks))
    else:
        llm = []
    findings = list(deterministic) + list(llm)
    findings.sort(key=lambda f: (f.file_path, f.line_number, f.rule_id))
    return findings


def _unknown_manifest(
    entry: RegistryEntry,
    *,
    config: PipelineConfig,
    audit_id: str,
    started_at: str,
    finished_at: str,
    reason: str,
) -> AuditManifest:
    return AuditManifest(
        audit_id=audit_id,
        auditor=Auditor(
            name=config.auditor_name,
            github=config.auditor_github,
            org=config.auditor_org,
        ),
        target=Target(
            repo_url=entry.repository_url or entry.name,
            commit_hash="",
            version=entry.version,
        ),
        audit_metadata=AuditMetadata(
            started_at=started_at,
            finished_at=finished_at,
            status="unknown",
            time_spent_minutes=0.0,
            verdict=VERDICT_UNKNOWN,
            integrity={"reason": reason},
        ),
        findings_summary=findings_summary([]),
        tools_used=(f"mcp-verified/{config.project_version}",),
    )


def audit_one(
    entry: RegistryEntry,
    *,
    config: PipelineConfig,
    writer: AuditDirWriter,
) -> CandidateOutcome:
    """Audit one registry entry. Always returns a `CandidateOutcome`.

    The caller is responsible for incrementing the run summary; this
    function does not mutate anything outside the configured `out_dir`.
    """
    started_at = _now_iso()
    start_clock = datetime.now(timezone.utc)

    # 1. Non-GitHub or no repo URL: unknown without ever cloning.
    if not entry.is_github_source or not entry.repository_url:
        finished_at = _now_iso()
        # Build a manifest under a synthetic target path so the
        # verdict registry still records the candidate.
        target_dir_url = entry.repository_url or f"unknown://{entry.name}"
        date = _date_yyyy_mm_dd()
        target_for_seq = config.out_dir / "audits" / "unknown" / entry.name.replace(
            "/", "_"
        )
        sequence = _next_sequence_for(config.auditor_name, date, target_for_seq)
        audit_id = build_audit_id(config.auditor_name, date, sequence)
        manifest = AuditManifest(
            audit_id=audit_id,
            auditor=Auditor(
                name=config.auditor_name,
                github=config.auditor_github,
                org=config.auditor_org,
            ),
            target=Target(
                repo_url=target_dir_url,
                commit_hash="",
                version=entry.version,
            ),
            audit_metadata=AuditMetadata(
                started_at=started_at,
                finished_at=finished_at,
                status="unknown",
                time_spent_minutes=0.0,
                verdict=VERDICT_UNKNOWN,
                integrity={"reason": "candidate is not a GitHub-published source"},
            ),
            findings_summary=findings_summary([]),
            tools_used=(f"mcp-verified/{config.project_version}",),
        )
        try:
            audit_dir = writer.write(manifest, [])
        except ValueError:
            audit_dir = _write_unknown_outcome(
                config.out_dir, manifest, [], bucket="_unknown"
            )
        return CandidateOutcome(
            entry=entry,
            verdict=VERDICT_UNKNOWN,
            audit_dir=audit_dir,
            findings=(),
            elapsed_seconds=0.0,
            status="unknown",
        )

    # 2. Attempt to clone and audit under the per-server budget.
    repo_url: str = entry.repository_url  # type: ignore[assignment]

    def _work() -> tuple[ClonedRepo, list[Finding]]:
        repo = safe_clone(repo_url)
        try:
            findings = _audit_cloned_tree(
                repo, provider=config.provider, checks=config.checks
            )
        except ProviderError as exc:
            repo.cleanup()
            raise exc
        return repo, findings

    try:
        result: BudgetResult[tuple[ClonedRepo, list[Finding]]] = run_with_budget(
            _work, timeout_seconds=config.per_server_budget_seconds
        )
    except CloneError as exc:
        finished_at = _now_iso()
        # Build an unknown-verdict manifest under a target-named directory.
        date = _date_yyyy_mm_dd()
        synthetic_target = config.out_dir / "audits" / "unknown" / entry.name.replace(
            "/", "_"
        )
        sequence = _next_sequence_for(config.auditor_name, date, synthetic_target)
        audit_id = build_audit_id(config.auditor_name, date, sequence)
        manifest = AuditManifest(
            audit_id=audit_id,
            auditor=Auditor(
                name=config.auditor_name,
                github=config.auditor_github,
                org=config.auditor_org,
            ),
            target=Target(repo_url=repo_url, commit_hash="", version=entry.version),
            audit_metadata=AuditMetadata(
                started_at=started_at,
                finished_at=finished_at,
                status="error",
                time_spent_minutes=0.0,
                verdict=VERDICT_UNKNOWN,
                integrity={"reason": f"clone failed: {exc}"},
            ),
            findings_summary=findings_summary([]),
            tools_used=(f"mcp-verified/{config.project_version}",),
        )
        try:
            audit_dir = writer.write(manifest, [])
        except ValueError:
            audit_dir = _write_unknown_outcome(
                config.out_dir, manifest, [], bucket="_unknown"
            )
        return CandidateOutcome(
            entry=entry,
            verdict=VERDICT_UNKNOWN,
            audit_dir=audit_dir,
            findings=(),
            elapsed_seconds=0.0,
            status="error",
        )

    if not result.completed:
        finished_at = _now_iso()
        date = _date_yyyy_mm_dd()
        # We don't have a commit hash; place under the repo URL as best we can.
        synthetic_target = config.out_dir / "audits" / "_pending" / entry.name.replace(
            "/", "_"
        )
        sequence = _next_sequence_for(config.auditor_name, date, synthetic_target)
        audit_id = build_audit_id(config.auditor_name, date, sequence)
        manifest = AuditManifest(
            audit_id=audit_id,
            auditor=Auditor(
                name=config.auditor_name,
                github=config.auditor_github,
                org=config.auditor_org,
            ),
            target=Target(repo_url=repo_url, commit_hash="", version=entry.version),
            audit_metadata=AuditMetadata(
                started_at=started_at,
                finished_at=finished_at,
                status="timeout",
                time_spent_minutes=config.per_server_budget_seconds / 60.0,
                verdict=VERDICT_UNKNOWN,
                integrity={"reason": "per-server wall-clock budget exceeded"},
            ),
            findings_summary=findings_summary([timeout_finding(config.per_server_budget_seconds)]),
            tools_used=(f"mcp-verified/{config.project_version}",),
        )
        timeout_marker = timeout_finding(config.per_server_budget_seconds)
        try:
            audit_dir = writer.write(manifest, [timeout_marker])
        except ValueError:
            audit_dir = _write_unknown_outcome(
                config.out_dir, manifest, [timeout_marker], bucket="_pending"
            )
        return CandidateOutcome(
            entry=entry,
            verdict=VERDICT_UNKNOWN,
            audit_dir=audit_dir,
            findings=(timeout_marker,),
            elapsed_seconds=result.elapsed_seconds,
            status="timeout",
        )

    repo, findings = result.value  # type: ignore[misc]
    commit_hash = repo.commit_hash
    try:
        verdict = aggregate_verdict(findings, audit_completed=True)
        finished_at = _now_iso()
        elapsed = (datetime.now(timezone.utc) - start_clock).total_seconds()
        date = _date_yyyy_mm_dd()
        target_dir = config.out_dir / "audits" / "github.com"
        sequence_dir = config.out_dir
        # build a probe target for sequence numbering
        host, owner, repo_name = (
            "github.com",
            repo_url.split("/")[-2],
            repo_url.rsplit("/", 1)[-1].removesuffix(".git"),
        )
        seq_probe = sequence_dir / "audits" / host / owner / repo_name
        sequence = _next_sequence_for(config.auditor_name, date, seq_probe)
        audit_id = build_audit_id(config.auditor_name, date, sequence)
        manifest = AuditManifest(
            audit_id=audit_id,
            auditor=Auditor(
                name=config.auditor_name,
                github=config.auditor_github,
                org=config.auditor_org,
            ),
            target=Target(
                repo_url=repo_url,
                commit_hash=commit_hash,
                version=entry.version,
            ),
            audit_metadata=AuditMetadata(
                started_at=started_at,
                finished_at=finished_at,
                status="completed",
                time_spent_minutes=elapsed / 60.0,
                verdict=verdict,
                integrity={"tree_commit": commit_hash},
            ),
            findings_summary=findings_summary(findings),
            tools_used=(
                f"mcp-verified/{config.project_version}",
                f"provider/{config.provider.name}",
            ),
        )
        audit_dir = writer.write(manifest, findings)
        return CandidateOutcome(
            entry=entry,
            verdict=verdict,
            audit_dir=audit_dir,
            findings=tuple(findings),
            elapsed_seconds=elapsed,
            status="completed",
        )
    finally:
        repo.cleanup()


def run_audit(
    entries: list[RegistryEntry],
    *,
    config: PipelineConfig,
) -> RunSummary:
    writer = AuditDirWriter(root_dir=config.out_dir)
    outcomes: list[CandidateOutcome] = []
    counters = {
        "verified": 0,
        "caution": 0,
        "risky": 0,
        "unknown": 0,
        "timeout": 0,
        "error": 0,
    }
    for entry in entries:
        outcome = audit_one(entry, config=config, writer=writer)
        outcomes.append(outcome)
        if outcome.status == "timeout":
            counters["timeout"] += 1
        elif outcome.status == "error":
            counters["error"] += 1
        if outcome.verdict in counters:
            counters[outcome.verdict] += 1
    return RunSummary(
        audited=len(outcomes),
        verified=counters["verified"],
        caution=counters["caution"],
        risky=counters["risky"],
        unknown=counters["unknown"],
        timeout=counters["timeout"],
        error=counters["error"],
        outcomes=tuple(outcomes),
    )
