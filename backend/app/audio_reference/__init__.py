"""Audio-reference-to-generation-profile analysis (spec: docs/audio_reference_to_generation_profile_spec.md).

Given a single local audio file, the baseline decodes it to canonical PCM,
measures quality / time-axis / harmony / acoustics observations, translates
them into a typed profile patch plus a capability report, and records a
reproducibility receipt.  Heavy analysis libraries (librosa, Essentia, ...)
are adapter workers, not core dependencies; this package is the pure-Python
CPU baseline.
"""

from __future__ import annotations

from .analysis import ANALYSIS_SCHEMA, ANALYSIS_SCHEMA_VERSION, build_analysis
from .capability import REPORT_SCHEMA, REPORT_SCHEMA_VERSION, build_capability_report
from .decode import DecodedAudio, DecodeError, decode_audio, decode_conditions
from .input_policy import InputPolicy, InputPolicyError, default_policy, policy_hash
from .observations import MODEL_ID, MODEL_VERSION
from .pipeline import PipelineError, analyze_reference_audio
from .receipt import RECEIPT_SCHEMA, RECEIPT_SCHEMA_VERSION, build_receipt
from .targets import Target, TargetError, resolve_target, require_executable
from .translation import PATCH_SCHEMA, PATCH_SCHEMA_VERSION, build_profile_patch, merge_profile_patch

__all__ = [
    "ANALYSIS_SCHEMA",
    "ANALYSIS_SCHEMA_VERSION",
    "REPORT_SCHEMA",
    "REPORT_SCHEMA_VERSION",
    "RECEIPT_SCHEMA",
    "RECEIPT_SCHEMA_VERSION",
    "PATCH_SCHEMA",
    "PATCH_SCHEMA_VERSION",
    "MODEL_ID",
    "MODEL_VERSION",
    "InputPolicy",
    "InputPolicyError",
    "DecodeError",
    "PipelineError",
    "TargetError",
    "DecodedAudio",
    "Target",
    "default_policy",
    "policy_hash",
    "decode_audio",
    "decode_conditions",
    "build_analysis",
    "build_profile_patch",
    "merge_profile_patch",
    "build_capability_report",
    "build_receipt",
    "resolve_target",
    "require_executable",
    "analyze_reference_audio",
]
