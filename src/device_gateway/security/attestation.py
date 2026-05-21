import hashlib
import json
import time
import uuid


def hash_program(program: str) -> str:
    """Return SHA-256 hex digest of an OpenQASM 3 program string."""
    return hashlib.sha256(program.encode("utf-8")).hexdigest()


def hash_counts(counts: dict[str, int]) -> str:
    """Return SHA-256 hex digest of canonical JSON representation of counts."""
    canonical = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_device_info(device_id: str, calibrated_at: str) -> str:
    """Return SHA-256 hex digest of device_id concatenated with calibrated_at."""
    payload = device_id + calibrated_at
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_job_attestation(
    job_id: str,
    program: str,
    counts: dict[str, int],
    device_id: str,
    calibrated_at: str = "",
) -> dict:
    """Create an integrity attestation record for a completed job.

    Returns a dict containing hashes, timestamp, and a unique attestation id.
    """
    return {
        "job_id": job_id,
        "program_hash": hash_program(program),
        "counts_hash": hash_counts(counts),
        "device_info_hash": hash_device_info(device_id, calibrated_at),
        "timestamp": time.time(),
        "attestation_id": str(uuid.uuid4()),
    }


def verify_attestation(
    attestation: dict,
    program: str,
    counts: dict[str, int],
) -> bool:
    """Verify that program and counts match the hashes stored in an attestation."""
    return (
        attestation.get("program_hash") == hash_program(program)
        and attestation.get("counts_hash") == hash_counts(counts)
    )
