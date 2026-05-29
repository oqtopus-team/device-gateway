"""Generate device topology JSON from local Qubex calibration files."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import yaml  # type: ignore[import]
from matplotlib import pyplot as plt

POSITION_DIVISOR = 30
POSITION_SCALE = 50


def qid_to_label(qid: int | str, num_qubits: int) -> str:
    """Convert a numeric qubit id to the Qubex/QDash label format."""
    qid_str = str(qid)
    if not re.fullmatch(r"\d+", qid_str):
        raise ValueError(f"Invalid qubit id: {qid}")
    width = max(2, len(str(num_qubits)))
    return "Q" + qid_str.zfill(width)


def label_to_qid(label: str) -> int:
    """Convert Qubex/QDash labels such as Q03 or Q143 to integer ids."""
    if not re.fullmatch(r"Q\d+", label):
        raise ValueError(f"Invalid qubit label: {label}")
    return int(label[1:])


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_request(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Request JSON not found: {path}")
    return load_json(path)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_metric(params_dir: Path | None, metric: str) -> dict[str, Any]:
    """Load a qubex-config params metric file.

    The expected format is:

    meta: ...
    data:
      Q00: 0.99
    """
    if params_dir is None:
        return {}
    path = params_dir / f"{metric}.yaml"
    if not path.exists():
        return {}
    data = load_yaml(path).get("data", {})
    return data if isinstance(data, dict) else {}


def metric_value(
    metrics: dict[str, dict[str, Any]],
    metric: str,
    label: str,
    fallback: float,
) -> float:
    value = metrics.get(metric, {}).get(label)
    if value is None:
        return fallback
    return float(value)


def coupling_metric_value(
    metrics: dict[str, dict[str, Any]],
    metric: str,
    control_label: str,
    target_label: str,
    fallback: float,
) -> float:
    values = metrics.get(metric, {})
    value = values.get(f"{control_label}-{target_label}")
    if value is None:
        value = values.get(f"{target_label}-{control_label}")
    if value is None:
        return fallback
    return float(value)


def infer_num_qubits(
    calib_note: dict[str, Any],
    params_dir: Path | None,
    explicit_qubits: list[int] | None,
) -> int:
    if explicit_qubits:
        return max(explicit_qubits) + 1

    qids: set[int] = set()
    for section_name in (
        "drag_hpi_params",
        "drag_pi_params",
        "hpi_params",
        "pi_params",
        "rabi_params",
        "state_params",
    ):
        section = calib_note.get(section_name, {})
        if isinstance(section, dict):
            for key in section:
                if re.fullmatch(r"Q\d+", key):
                    qids.add(label_to_qid(key))

    cr_params = calib_note.get("cr_params", {})
    if isinstance(cr_params, dict):
        for key in cr_params:
            for label in key.split("-"):
                if re.fullmatch(r"Q\d+", label):
                    qids.add(label_to_qid(label))

    if params_dir is not None:
        for metric in ("x90_gate_fidelity", "average_readout_fidelity", "t1", "t2_echo"):
            for key in load_metric(params_dir, metric):
                if re.fullmatch(r"Q\d+", key):
                    qids.add(label_to_qid(key))

    if not qids:
        raise ValueError("Could not infer qubits from calibration note or params")
    return max(qids) + 1


def infer_qubits(
    calib_note: dict[str, Any],
    metrics: dict[str, dict[str, Any]],
    num_qubits: int,
    explicit_qubits: list[int] | None,
) -> list[int]:
    if explicit_qubits is not None:
        return sorted(explicit_qubits)

    qids: set[int] = set()
    for metric in ("x90_gate_fidelity", "average_readout_fidelity", "t1", "t2_echo"):
        for label, value in metrics.get(metric, {}).items():
            if value is not None and re.fullmatch(r"Q\d+", label):
                qids.add(label_to_qid(label))

    for section_name in (
        "drag_hpi_params",
        "drag_pi_params",
        "hpi_params",
        "pi_params",
        "rabi_params",
        "state_params",
    ):
        section = calib_note.get(section_name, {})
        if isinstance(section, dict):
            for label in section:
                if re.fullmatch(r"Q\d+", label):
                    qids.add(label_to_qid(label))

    if not qids:
        qids = set(range(num_qubits))
    return sorted(qid for qid in qids if 0 <= qid < num_qubits)


def generate_square_lattice_mux_topology(num_qubits: int, mux_size: int = 2) -> dict[str, Any]:
    """Generate the same MUX ordering used by QDash square-lattice topology files."""
    grid_size = math.isqrt(num_qubits)
    if grid_size * grid_size != num_qubits:
        raise ValueError(
            f"Cannot auto-generate square lattice for {num_qubits} qubits. "
            "Pass --topology-yaml for non-square devices."
        )
    qubits: dict[int, dict[str, int]] = {}
    small_size = mux_size * mux_size
    mux_cols = grid_size // mux_size

    for qid in range(num_qubits):
        mux_index, small_index = divmod(qid, small_size)
        mux_row, mux_col = divmod(mux_index, mux_cols)
        small_row, small_col = divmod(small_index, mux_size)
        qubits[qid] = {
            "row": mux_row * mux_size + small_row,
            "col": mux_col * mux_size + small_col,
        }

    couplings: list[list[int]] = []
    for source, pos in qubits.items():
        for target, target_pos in qubits.items():
            if target <= source:
                continue
            distance = abs(pos["row"] - target_pos["row"]) + abs(pos["col"] - target_pos["col"])
            if distance == 1:
                couplings.append([source, target])

    return {
        "name": "Square Lattice with MUX",
        "num_qubits": num_qubits,
        "grid_size": grid_size,
        "qubits": qubits,
        "couplings": couplings,
    }


def load_topology(
    num_qubits: int,
    topology_yaml: Path | None,
    qdash_repo: Path | None,
) -> dict[str, Any]:
    if topology_yaml is not None:
        return normalize_topology(load_yaml(topology_yaml))
    if qdash_repo is not None:
        candidate = (
            qdash_repo
            / "config"
            / "domain"
            / "topologies"
            / f"square-lattice-mux-{num_qubits}.yaml"
        )
        if candidate.exists():
            return normalize_topology(load_yaml(candidate))
    return normalize_topology(generate_square_lattice_mux_topology(num_qubits))


def normalize_topology(topology: dict[str, Any]) -> dict[str, Any]:
    qubits = topology.get("qubits", {})
    if isinstance(qubits, dict):
        topology["qubits"] = {int(qid): pos for qid, pos in qubits.items()}
    topology["couplings"] = [
        [int(control), int(target)]
        for control, target in topology.get("couplings", [])
    ]
    return topology


def parse_qubit_list(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    if not raw.strip():
        return []
    return sorted({int(part.strip()) for part in raw.split(",")})


def parse_exclude_couplings(raw: str | None) -> set[tuple[int, int]]:
    if raw is None or not raw.strip():
        return set()
    excluded = set()
    for item in raw.split(","):
        left, right = item.strip().split("-")
        excluded.add(tuple(sorted((int(left), int(right)))))
    return excluded


def build_device_topology(
    *,
    calib_note_path: Path,
    params_dir: Path | None = None,
    topology_yaml: Path | None = None,
    qdash_repo: Path | None = None,
    name: str = "anemone",
    device_id: str = "anemone",
    qubits: list[int] | None = None,
    exclude_couplings: set[tuple[int, int]] | None = None,
    qubit_fidelity_metric: str = "x90_gate_fidelity",
    coupling_fidelity_metric: str = "zx90_gate_fidelity",
    qubit_fidelity_range: tuple[float, float] = (0.0, 1.0),
    coupling_fidelity_range: tuple[float, float] = (0.0, 1.0),
    readout_fidelity_range: tuple[float, float] = (0.0, 1.0),
    only_maximum_connected: bool = True,
) -> dict[str, Any]:
    """Build device topology with QDash-compatible fields."""
    calib_note = load_json(calib_note_path)
    num_qubits = infer_num_qubits(calib_note, params_dir, qubits)
    topology = load_topology(num_qubits, topology_yaml, qdash_repo)
    num_qubits = int(topology.get("num_qubits", num_qubits))

    def label(qid: int) -> str:
        return qid_to_label(qid, num_qubits)

    metrics = {
        metric: load_metric(params_dir, metric)
        for metric in {
            "x90_gate_fidelity",
            "zx90_gate_fidelity",
            qubit_fidelity_metric,
            coupling_fidelity_metric,
            "t1",
            "t2_echo",
            "readout_fidelity_0",
            "readout_fidelity_1",
            "average_readout_fidelity",
        }
    }
    physical_ids = infer_qubits(calib_note, metrics, num_qubits, qubits)
    physical_ids = [qid for qid in physical_ids if qid in topology.get("qubits", {})]
    id_mapping = {qid: idx for idx, qid in enumerate(physical_ids)}
    excluded = exclude_couplings or set()

    qubit_entries = []
    for qid in physical_ids:
        qubit_label = label(qid)
        qubit_pos = topology["qubits"][qid]
        readout_fidelity_0 = metric_value(
            metrics, "readout_fidelity_0", qubit_label, fallback=0.75
        )
        readout_fidelity_1 = metric_value(
            metrics, "readout_fidelity_1", qubit_label, fallback=0.75
        )
        if readout_fidelity_0 == 0.75 and readout_fidelity_1 == 0.75:
            average_readout_fidelity = metric_value(
                metrics, "average_readout_fidelity", qubit_label, fallback=0.75
            )
            readout_fidelity_0 = average_readout_fidelity
            readout_fidelity_1 = average_readout_fidelity

        drag_hpi = calib_note.get("drag_hpi_params", {}).get(qubit_label, {})
        drag_pi = calib_note.get("drag_pi_params", {}).get(qubit_label, {})
        qubit_entries.append(
            {
                "id": id_mapping[qid],
                "physical_id": qid,
                "position": {
                    "x": qubit_pos["col"] * POSITION_SCALE / POSITION_DIVISOR,
                    "y": -1 * qubit_pos["row"] * POSITION_SCALE / POSITION_DIVISOR,
                },
                "fidelity": metric_value(
                    metrics, qubit_fidelity_metric, qubit_label, fallback=0.25
                ),
                "meas_error": {
                    "prob_meas1_prep0": 1 - readout_fidelity_0,
                    "prob_meas0_prep1": 1 - readout_fidelity_1,
                    "readout_assignment_error": 1
                    - ((readout_fidelity_0 + readout_fidelity_1) / 2),
                },
                "qubit_lifetime": {
                    "t1": metric_value(metrics, "t1", qubit_label, fallback=100.0),
                    "t2": metric_value(metrics, "t2_echo", qubit_label, fallback=100.0),
                },
                "gate_duration": {
                    "rz": 0,
                    "sx": int(drag_hpi.get("duration", 20)),
                    "x": int(drag_pi.get("duration", 20)),
                },
            }
        )

    if qubit_entries:
        min_x = min(q["position"]["x"] for q in qubit_entries)
        min_y = min(q["position"]["y"] for q in qubit_entries)
        for qubit in qubit_entries:
            qubit["position"]["x"] -= min_x
            qubit["position"]["y"] -= min_y

    cr_params = calib_note.get("cr_params", {})
    measured_cr_pairs = set(cr_params) if isinstance(cr_params, dict) else set()
    topology_couplings = topology.get("couplings", [])
    coupling_entries = []
    for control, target in topology_couplings:
        control_label = label(control)
        target_label = label(target)
        cr_key = f"{control_label}-{target_label}"
        reverse_cr_key = f"{target_label}-{control_label}"
        if cr_key in measured_cr_pairs:
            directed_control, directed_target = control, target
            cr_value = cr_params[cr_key]
        elif reverse_cr_key in measured_cr_pairs:
            directed_control, directed_target = target, control
            cr_value = cr_params[reverse_cr_key]
        else:
            continue

        if directed_control not in id_mapping or directed_target not in id_mapping:
            continue
        if tuple(sorted((directed_control, directed_target))) in excluded:
            continue

        coupling_entries.append(
            {
                "control": id_mapping[directed_control],
                "target": id_mapping[directed_target],
                "fidelity": coupling_metric_value(
                    metrics,
                    coupling_fidelity_metric,
                    label(directed_control),
                    label(directed_target),
                    fallback=0.25,
                ),
                "gate_duration": {"rzx90": int(cr_value.get("duration", 20))},
            }
        )

    qubit_entries, coupling_entries = apply_filters(
        qubit_entries,
        coupling_entries,
        qubit_fidelity_range,
        coupling_fidelity_range,
        readout_fidelity_range,
    )
    if only_maximum_connected:
        qubit_entries, coupling_entries = extract_largest_component(
            qubit_entries, coupling_entries
        )

    return {
        "name": name,
        "device_id": device_id,
        "qubits": qubit_entries,
        "couplings": coupling_entries,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
    }


def apply_filters(
    qubits: list[dict[str, Any]],
    couplings: list[dict[str, Any]],
    qubit_fidelity_range: tuple[float, float],
    coupling_fidelity_range: tuple[float, float],
    readout_fidelity_range: tuple[float, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filtered_qubits = [
        q
        for q in qubits
        if qubit_fidelity_range[0] <= q["fidelity"] <= qubit_fidelity_range[1]
    ]
    filtered_qubits = [
        q
        for q in filtered_qubits
        if readout_fidelity_range[0]
        <= 1 - q["meas_error"]["readout_assignment_error"]
        <= readout_fidelity_range[1]
    ]
    valid_qubit_ids = {q["id"] for q in filtered_qubits}
    filtered_couplings = [
        c
        for c in couplings
        if coupling_fidelity_range[0] <= c["fidelity"] <= coupling_fidelity_range[1]
        and c["control"] in valid_qubit_ids
        and c["target"] in valid_qubit_ids
    ]
    return filtered_qubits, filtered_couplings


def extract_largest_component(
    qubits: list[dict[str, Any]], couplings: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graph = nx.Graph()
    graph.add_edges_from((c["control"], c["target"]) for c in couplings)
    components = list(nx.connected_components(graph))
    if not components:
        return qubits, couplings

    largest = max(components, key=len)
    filtered_qubits = [q for q in qubits if q["id"] in largest]
    filtered_couplings = [
        c for c in couplings if c["control"] in largest and c["target"] in largest
    ]
    new_id_mapping = {q["id"]: index for index, q in enumerate(filtered_qubits)}
    for qubit in filtered_qubits:
        qubit["id"] = new_id_mapping[qubit["id"]]
    for coupling in filtered_couplings:
        coupling["control"] = new_id_mapping[coupling["control"]]
        coupling["target"] = new_id_mapping[coupling["target"]]
    return filtered_qubits, filtered_couplings


def parse_range(raw: str) -> tuple[float, float]:
    left, right = raw.split(":")
    return float(left), float(right)


def range_from_condition(
    request: dict[str, Any],
    key: str,
    fallback: tuple[float, float] = (0.0, 1.0),
) -> tuple[float, float]:
    condition = request.get("condition", {})
    fidelity_condition = condition.get(key, {})
    return (
        float(fidelity_condition.get("min", fallback[0])),
        float(fidelity_condition.get("max", fallback[1])),
    )


def metric_from_condition(request: dict[str, Any], key: str, fallback: str) -> str:
    condition = request.get("condition", {})
    fidelity_condition = condition.get(key, {})
    return str(fidelity_condition.get("metric") or fallback)


def dump_topology_png(topology: dict[str, Any], output_png: Path) -> None:
    graph = nx.Graph()
    pos = {}
    for qubit in topology["qubits"]:
        graph.add_node(qubit["id"])
        pos[qubit["id"]] = (qubit["position"]["x"], qubit["position"]["y"])
    for coupling in topology["couplings"]:
        graph.add_edge(coupling["control"], coupling["target"])
    plt.figure(figsize=(5, 5))
    nx.draw(
        graph,
        pos=pos,
        with_labels=True,
        node_color="white",
        edge_color="black",
        font_color="black",
    )
    plt.savefig(output_png)
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate device topology JSON from local Qubex calibration files."
    )
    parser.add_argument("--calib-note", type=Path, required=True)
    parser.add_argument(
        "--request-json",
        type=Path,
        help="QDash-compatible device_topology_request.json.",
    )
    parser.add_argument("--params-dir", type=Path)
    parser.add_argument("--topology-yaml", type=Path)
    parser.add_argument("--qdash-repo", type=Path)
    parser.add_argument("--output-json", type=Path, default=Path("config/device_topology.json"))
    parser.add_argument("--output-png", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--device-id")
    parser.add_argument("--qubits", help="Comma-separated physical qubit ids. Defaults to inferred.")
    parser.add_argument(
        "--exclude-couplings",
        help="Comma-separated physical couplings, e.g. 0-1,3-1.",
    )
    parser.add_argument(
        "--keep-disconnected",
        action="store_true",
        help="Keep disconnected components instead of matching QDash's largest-component filter.",
    )
    parser.add_argument("--qubit-fidelity-range", default="0.0:1.0")
    parser.add_argument("--coupling-fidelity-range", default="0.0:1.0")
    parser.add_argument("--readout-fidelity-range", default="0.0:1.0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request = load_request(args.request_json)
    request_condition = request.get("condition", {})
    topology = build_device_topology(
        calib_note_path=args.calib_note,
        params_dir=args.params_dir,
        topology_yaml=args.topology_yaml,
        qdash_repo=args.qdash_repo,
        name=args.name or request.get("name", "anemone"),
        device_id=args.device_id or request.get("device_id", "anemone"),
        qubits=parse_qubit_list(args.qubits)
        if args.qubits is not None
        else parse_qubit_list(",".join(request.get("qubits", [])))
        if request.get("qubits") is not None
        else None,
        exclude_couplings=parse_exclude_couplings(args.exclude_couplings)
        if args.exclude_couplings is not None
        else parse_exclude_couplings(",".join(request.get("exclude_couplings", []))),
        qubit_fidelity_metric=metric_from_condition(
            request, "qubit_fidelity", "x90_gate_fidelity"
        ),
        coupling_fidelity_metric=metric_from_condition(
            request, "coupling_fidelity", "zx90_gate_fidelity"
        ),
        qubit_fidelity_range=parse_range(args.qubit_fidelity_range)
        if args.qubit_fidelity_range != "0.0:1.0" or "condition" not in request
        else range_from_condition(request, "qubit_fidelity"),
        coupling_fidelity_range=parse_range(args.coupling_fidelity_range)
        if args.coupling_fidelity_range != "0.0:1.0" or "condition" not in request
        else range_from_condition(request, "coupling_fidelity"),
        readout_fidelity_range=parse_range(args.readout_fidelity_range)
        if args.readout_fidelity_range != "0.0:1.0" or "condition" not in request
        else range_from_condition(request, "readout_fidelity"),
        only_maximum_connected=False
        if args.keep_disconnected
        else bool(request_condition.get("only_maximum_connected", True)),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(topology, indent=2) + "\n", encoding="utf-8")
    if args.output_png is not None:
        args.output_png.parent.mkdir(parents=True, exist_ok=True)
        dump_topology_png(topology, args.output_png)


if __name__ == "__main__":
    main()
