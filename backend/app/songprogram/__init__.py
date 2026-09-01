"""Deterministic GEN0 SongProgram resolvers."""

from .compiler import CompileError, CompilerIdentity, build_lineage_index, compile_direct_sp0
from .resolver import resolve_joint_bnb, resolve_progression
from .renderer import RenderError, RenderResult, render_reference
from .search import (
    ArchiveCandidate,
    LocalRunStore,
    action_id,
    canonical_bytes,
    descriptor_values,
    descriptor_result_from_project,
    fingerprint_distance_q,
    fingerprint_payloads_from_project,
    fingerprint_record,
    fingerprint_record_from_project,
    manifest_digest,
    sampler_choice,
    seal_record,
    update_archive_record,
)
from .validator import ProjectValidationError, validate_project

__all__ = [
    "ArchiveCandidate",
    "CompileError",
    "CompilerIdentity",
    "LocalRunStore",
    "RenderError",
    "RenderResult",
    "ProjectValidationError",
    "action_id",
    "canonical_bytes",
    "build_lineage_index",
    "compile_direct_sp0",
    "descriptor_values",
    "descriptor_result_from_project",
    "fingerprint_distance_q",
    "fingerprint_payloads_from_project",
    "fingerprint_record",
    "fingerprint_record_from_project",
    "manifest_digest",
    "resolve_joint_bnb",
    "resolve_progression",
    "render_reference",
    "sampler_choice",
    "seal_record",
    "update_archive_record",
    "validate_project",
]
