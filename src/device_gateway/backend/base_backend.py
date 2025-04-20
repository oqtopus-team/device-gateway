import json
import logging
from abc import ABCMeta

logger = logging.getLogger("device_gateway")


class BaseBackend(metaclass=ABCMeta):
    """
    BaseBackend handles the execution of a compiled circuit on quantum hardware.
    It no longer provides gate-level operations.
    """

    def __init__(self, config: dict):
        """
        Initialize the backend with a virtual-to-physical qubit mapping.
        This is done once at server startup.
        """
        self.config = config

    def load_device_topology(self):
        """
        Load the device topology from a JSON file.
        """
        with open(self.config["device_topology_json_path"]) as f:
            device_topology = json.load(f)
        return device_topology

    def save_device_topology(self, device_topology):
        with open(self.config["device_topology_json_path"], "w") as f:
            json.dump(device_topology, f, indent=4)

    def is_active(self) -> bool:
        """
        Check if the device is active.
        """
        return self.config["device_status"] == "active"

    def is_inactive(self) -> bool:
        """
        Check if the device is inactive.
        """
        return self.config["device_status"] == "inactive"

    def is_maintenance(self) -> bool:
        """
        Check if the device is in maintenance.
        """
        return self.config["device_status"] == "maintenance"

    def is_simulator(self) -> bool:
        """
        Check if the device is a simulator.
        """
        return self.config["simulator_mode"]

    def is_qpu(self) -> bool:
        """
        Check if the device is a QPU.
        """
        return not self.config["simulator_mode"]

    @property
    def device_topology(self) -> dict:
        """
        Returns the device topology, e.g., {"qubits": [{"id": 0, "physical_id": 5}], "couplings": [{"control": 0, "target": 1}]}
        """
        return self.load_device_topology()

    @property
    def device_status(self) -> dict:
        """
        Returns the device status, e.g., {"status": "OK", "message": "Device is operational"}
        """
        return self.config["device_status"]

    @property
    def device_info(self) -> dict:
        """
        Returns the device information, e.g., {"device_id": "QPU1", "device_type": "QPU"}
        """
        if self.is_simulator():
            self.config["device_info"]["type"] = "simulator"
        else:
            self.config["device_info"]["type"] = "QPU"
        return self.config["device_info"]

    @property
    def virtual_physical_map(self):
        device_topology = self.load_device_topology()
        qubits = {
            qubit["id"]: f"Q{qubit['physical_id']:02}"
            for qubit in device_topology["qubits"]
        }
        couplings = {
            (c["control"], c["target"]): (
                qubits[c["control"]],
                qubits[c["target"]],
            )
            for c in device_topology["couplings"]
        }
        return {"qubits": qubits, "couplings": couplings}

    @property
    def qubits(self) -> list:
        """
        Returns a list of qubit labels, e.g., ["Q05", "Q07"]
        """
        return list(self.virtual_physical_map["qubits"].values())  # type: ignore

    @property
    def couplings(self) -> list:
        """
        Returns a list of couplings in the format "QXX-QYY", e.g., ["Q05-Q07", "Q07-Q05"]
        """
        return [
            f"{v[0]}-{v[1]}"
            for v in self.virtual_physical_map["couplings"].values()  # type: ignore
        ]  # type: ignore

    @property
    def virtual_physical_qubits(self) -> dict:
        """
        Returns the virtual-to-physical mapping, e.g., {0: "Q05", 1: "Q07"}
        """
        # Return a shallow copy to avoid accidental modifications
        return self.virtual_physical_map["qubits"].copy()  # type: ignore

    @property
    def physical_virtual_qubits(self) -> dict:
        """
        Returns the physical-to-virtual mapping, e.g., {"Q05": 0, "Q07": 1}
        """
        return {v: k for k, v in self.virtual_physical_qubits.items()}

    def physical_qubit(self, virtual_qubit: str) -> str:
        """
        Returns the physical qubit corresponding to the virtual qubit.
        """
        return self.virtual_physical_qubits[virtual_qubit]

    def virtual_qubit(self, physical_qubit: str) -> int:
        """
        Returns the virtual qubit corresponding to the physical qubit.
        """
        return self.physical_virtual_qubits[physical_qubit]

    def execute(self, circuit, shots: int = 1024) -> dict:
        """
        Execute the compiled circuit for a specified number of shots.
        The compiled_circuit is produced by the Circuit class.
        Implement this method in the derived class.
        """
        raise NotImplementedError("This method is not implemented")
