"""Vendored subset of the Coworld reporter SDK from ``Metta-AI/reporters``.

Mirrored from metta's paintarena example
(``packages/coworld/src/coworld/examples/paintarena/reporter/_sdk_vendored``),
which is itself a pinned copy of ``reporters/reporter_sdk/reporter_sdk``.

We vendor only the pyarrow-free subset (bundle reader, URI I/O, deterministic
report-zip builder). The event-log Parquet writer is intentionally omitted:
stag_hunt's v1 reporter emits Markdown + JSON, so it carries no pyarrow
dependency. Do not edit these files here — treat upstream as the source of
truth and re-vendor if the contract changes.
"""

from .bundle import BundleInnerManifest, BundleReader
from .io import (
    ReporterInputs,
    load_reporter_inputs,
    read_json,
    read_uri,
    write_uri,
)
from .output_manifest import (
    EVENT_LOG_EXTENSIONS,
    RENDERABLE_EXTENSIONS,
    OutputManifest,
    build_report_zip,
)
from .zip_writer import MTIME_SENTINEL, stable_json, write_deterministic_zip

__all__ = [
    "EVENT_LOG_EXTENSIONS",
    "MTIME_SENTINEL",
    "RENDERABLE_EXTENSIONS",
    "BundleInnerManifest",
    "BundleReader",
    "OutputManifest",
    "ReporterInputs",
    "build_report_zip",
    "load_reporter_inputs",
    "read_json",
    "read_uri",
    "stable_json",
    "write_deterministic_zip",
    "write_uri",
]
