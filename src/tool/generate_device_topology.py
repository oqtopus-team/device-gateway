import json
import re

import yaml
from pydantic import BaseModel


class Position(BaseModel):
    """Position of the qubit on the device."""

    x: float
    y: float


class MeasError(BaseModel):
    """Measurement error of the qubit."""

    prob_meas1_prep0: float
    prob_meas0_prep1: float
    readout_assignment_error: float


class QubitLifetime(BaseModel):
    """Qubit lifetime of the qubit."""

    t1: float
    t2: float


class QubitGateDuration(BaseModel):
    """Gate duration of the qubit."""

    rz: int
    sx: int
    x: int


class Qubit(BaseModel):
    """Qubit information."""

    id: int
    physical_id: int
    position: Position
    fidelity: float
    meas_error: MeasError
    qubit_lifetime: QubitLifetime
    gate_duration: QubitGateDuration


class CouplingGateDuration(BaseModel):
    """Gate duration of the coupling."""

    rzx90: int


class Coupling(BaseModel):
    """Coupling information."""

    control: int
    target: int
    fidelity: float
    gate_duration: CouplingGateDuration


class Device(BaseModel):
    """Device information."""

    name: str
    device_id: str
    qubits: list[Qubit]
    couplings: list[Coupling]
    calibrated_at: str


def search_coupling_data_by_control_qid(cr_params: dict, search_term: str) -> dict:
    """Search for coupling data by control qubit id."""
    filtered = {}
    for key, value in cr_params.items():
        # キーが '-' を含む場合は、左側を抽出
        left_side = key.split("-")[0] if "-" in key else key
        if left_side == search_term:
            filtered[key] = value
    return filtered


def qid_to_label(qid: str) -> str:
    """Convert a numeric qid string to a label with at least two digits. e.g. '0' -> 'Q00'."""
    if re.fullmatch(r"\d+", qid):
        return "Q" + qid.zfill(2)
    error_message = "Invalid qid format."
    raise ValueError(error_message)


def normalize_coupling_key(control: str, target: str) -> str:
    """Normalize coupling key by sorting the qubits.

    This ensures that "0-1" and "1-0" are treated as the same coupling.
    """
    qubits = sorted([control, target])
    return f"{qubits[0]}-{qubits[1]}"


def split_q_string(cr_label: str) -> tuple[str, str]:
    """Split a string of the form "Q31-Q29" into two parts.

    Args:
    ----
        cr_label (str): "Q31-Q29" string.

    Returns:
    -------
        tuple: example ("31", "29") or ("4", "5") if the string is in the correct format.
               Leading zeros are removed.

    Raises:
    ------
        ValueError: If the input string is not in the correct format.

    """
    parts = cr_label.split("-")
    expected_parts_count = 2
    error_message = "Invalid format. Expected 'Q31-Q29' or 'Q31-Q29'."
    if len(parts) != expected_parts_count:
        raise ValueError(error_message)

    # Remove the leading 'Q' if present and convert to integer to remove leading zeros
    left = parts[0][1:] if parts[0].startswith("Q") else parts[0]
    right = parts[1][1:] if parts[1].startswith("Q") else parts[1]

    # Convert to integer to remove leading zeros, then back to string
    left = str(int(left))
    right = str(int(right))

    return left, right


class DeviceTopologyRequst(BaseModel):
    """Request model for device topology."""

    name: str = "anemone"
    device_id: str = "anemone"
    qubits: list[str] = ["0", "1", "2", "3", "4", "5"]
    exclude_couplings: list[str] = []


def load_qubit_config(yaml_path: str) -> dict:
    """
    指定した YAML ファイルを読み込み、Python の辞書として返す。

    Parameters
    ----------
    yaml_path : str
        読み込む YAML ファイルのパス。

    Returns
    -------
    dict
        YAML の内容を Python の辞書として保持したもの。
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def get_device_topology(
    request: DeviceTopologyRequst,
) -> Device:
    """Get the device topology."""

    couplings = []
    qubits = []

    def load_note(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d

    note = load_note("note.json")

    # chip_docs = ChipDocument.find_one({"chip_id": chip_id, "username": latest.username}).run()
    # Sort physical qubit indices and create id mapping

    sorted_physical_ids = request.qubits
    print(sorted_physical_ids)
    id_mapping = {pid: idx for idx, pid in enumerate(sorted_physical_ids)}
    path = "props.yaml"
    config = load_qubit_config(path)
    config = config["64Q"]

    def index_to_qubit_label(idx: int) -> str:
        return f"Q{idx:02d}"

    def load_device(path: str) -> Device:
        from pathlib import Path

        raw = Path(path).read_text(encoding="utf-8")
        return Device.parse_raw(raw)

    device = load_device("device_topology.json")

    for qid in request.qubits:
        x90_gate_fidelity = (
            config["x90_gate_fidelity"][index_to_qubit_label(int(qid))] or 0.99
        )
        t1 = config["t1"][index_to_qubit_label(int(qid))] or 10
        t2 = config["t2_echo"][index_to_qubit_label(int(qid))] or 10
        readout_fidelity_0 = 0.5
        readout_fidelity_1 = 0.5
        # Calculate readout assignment error
        prob_meas1_prep0 = 1 - readout_fidelity_0
        prob_meas0_prep1 = 1 - readout_fidelity_1
        # Calculate readout assignment error
        readout_assignment_error = 1 - (readout_fidelity_0 + readout_fidelity_1) / 2

        qubits.append(
            Qubit(
                id=id_mapping[qid],  # Map to new sequential id
                physical_id=int(qid),
                position=Position(
                    x=device.qubits[int(qid)].position.x,
                    y=device.qubits[int(qid)].position.y,
                ),
                fidelity=x90_gate_fidelity,
                meas_error=MeasError(
                    prob_meas1_prep0=prob_meas1_prep0,
                    prob_meas0_prep1=prob_meas0_prep1,
                    readout_assignment_error=readout_assignment_error,
                ),
                qubit_lifetime=QubitLifetime(
                    t1=t1,
                    t2=t2,
                ),
                gate_duration=QubitGateDuration(
                    rz=0,
                    sx=20,
                    x=40,
                ),
            )
        )

    cr_params = note["cr_params"]
    # Process couplings
    for qid in request.qubits:
        search_result = search_coupling_data_by_control_qid(
            cr_params, qid_to_label(qid)
        )
        for cr_key, cr_value in search_result.items():
            target = cr_value["target"]
            control, target = split_q_string(cr_key)
            cr_duration = cr_value.get("duration", 20)
            zx90_gate_fidelity = (
                config["zx90_gate_fidelity"][
                    f"{index_to_qubit_label(int(control))}-{index_to_qubit_label(int(target))}"
                ]
                or 0.9
            )
            # Only append if both control and target qubits exist in id_mapping and coupling is not excluded
            if control in id_mapping and target in id_mapping:
                # Normalize both the current coupling key and all excluded couplings
                current_coupling = normalize_coupling_key(control, target)
                excluded_couplings = {
                    normalize_coupling_key(*coupling.split("-"))
                    for coupling in request.exclude_couplings
                }

                if current_coupling not in excluded_couplings:
                    couplings.append(
                        Coupling(
                            control=id_mapping[control],  # Map to new sequential id
                            target=id_mapping[target],  # Map to new sequential id
                            fidelity=zx90_gate_fidelity,
                            gate_duration=CouplingGateDuration(rzx90=cr_duration),
                        )
                    )
    import pendulum

    return Device(
        name=request.name,
        device_id=request.device_id,
        qubits=qubits,
        couplings=couplings,
        calibrated_at=pendulum.now("UTC").to_iso8601_string(),
    )


if __name__ == "__main__":
    request = DeviceTopologyRequst(
        name="anemone",
        device_id="anemone",
        qubits=[
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "20",
            "21",
            "22",
            "23",
            "24",
            "25",
            "26",
            "27",
            "28",
            "29",
            "30",
            "31",
            "32",
            "33",
            "34",
            "35",
            "36",
            "37",
            "38",
            "39",
            "40",
            "41",
            "42",
            "43",
            "44",
            "45",
            "46",
            "47",
            "48",
            "49",
            "50",
            "51",
            "52",
            "53",
            "54",
            "55",
            "56",
            "57",
            "58",
            "59",
            "60",
            "61",
            "62",
            "63",
        ],
        exclude_couplings=[],
    )
    device_topo = get_device_topology(request)
    # save to json
    import json

    with open("new_device_topology.json", "w") as f:
        json.dump(device_topo.model_dump(exclude_none=True), f, indent=4)
