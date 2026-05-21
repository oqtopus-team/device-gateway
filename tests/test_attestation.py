import hashlib
import json

from device_gateway.security.attestation import (
    create_job_attestation,
    hash_counts,
    hash_device_info,
    hash_program,
    verify_attestation,
)

SAMPLE_PROGRAM = 'OPENQASM 3.0;\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\nbit[2] c;\nc = measure q;'
SAMPLE_COUNTS = {"00": 500, "11": 500}


def test_hash_program_known_output():
    expected = hashlib.sha256(SAMPLE_PROGRAM.encode("utf-8")).hexdigest()
    assert hash_program(SAMPLE_PROGRAM) == expected


def test_hash_program_deterministic():
    assert hash_program(SAMPLE_PROGRAM) == hash_program(SAMPLE_PROGRAM)


def test_hash_counts_known_output():
    canonical = json.dumps(SAMPLE_COUNTS, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert hash_counts(SAMPLE_COUNTS) == expected


def test_hash_counts_order_independent():
    counts_a = {"00": 500, "11": 500}
    counts_b = {"11": 500, "00": 500}
    assert hash_counts(counts_a) == hash_counts(counts_b)


def test_hash_device_info_known_output():
    device_id = "device-1"
    calibrated_at = "2025-01-01T00:00:00Z"
    payload = device_id + calibrated_at
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert hash_device_info(device_id, calibrated_at) == expected


def test_create_job_attestation_fields():
    att = create_job_attestation("job-1", SAMPLE_PROGRAM, SAMPLE_COUNTS, "dev-1")
    assert att["job_id"] == "job-1"
    assert att["program_hash"] == hash_program(SAMPLE_PROGRAM)
    assert att["counts_hash"] == hash_counts(SAMPLE_COUNTS)
    assert "timestamp" in att
    assert "attestation_id" in att


def test_verify_attestation_roundtrip():
    att = create_job_attestation("job-2", SAMPLE_PROGRAM, SAMPLE_COUNTS, "dev-1")
    assert verify_attestation(att, SAMPLE_PROGRAM, SAMPLE_COUNTS) is True


def test_verify_attestation_tampered_counts():
    att = create_job_attestation("job-3", SAMPLE_PROGRAM, SAMPLE_COUNTS, "dev-1")
    tampered = {"00": 999, "11": 1}
    assert verify_attestation(att, SAMPLE_PROGRAM, tampered) is False


def test_verify_attestation_tampered_program():
    att = create_job_attestation("job-4", SAMPLE_PROGRAM, SAMPLE_COUNTS, "dev-1")
    assert verify_attestation(att, "OPENQASM 3.0; // tampered", SAMPLE_COUNTS) is False
