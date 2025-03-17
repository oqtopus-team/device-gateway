import logging
from abc import ABCMeta

logger = logging.getLogger("device_gateway")


class BaseBackend(metaclass=ABCMeta):
    """
    BaseBackend handles the execution of a compiled circuit on quantum hardware.
    It no longer provides gate-level operations.
    """

    def __init__(self, virtual_physical_map: dict):
        """
        Initialize the backend with a virtual-to-physical qubit mapping.
        This is done once at server startup.
        """
        self._virtual_physical_map = {
            "qubits": {
                k: f"Q{v:02}" for k, v in virtual_physical_map["qubits"].items()
            },
            "couplings": {
                k: (f"Q{v[0]:02}", f"Q{v[1]:02}")
                for k, v in virtual_physical_map["couplings"].items()
            },
        }

    @property
    def qubits(self) -> list:
        """
        Returns a list of qubit labels, e.g., ["Q05", "Q07"]
        """
        return list(self._virtual_physical_map["qubits"].values())  # type: ignore

    @property
    def couplings(self) -> list:
        """
        Returns a list of couplings in the format "QXX-QYY", e.g., ["Q05-Q07", "Q07-Q05"]
        """
        return [
            f"{v[0]}-{v[1]}"
            for v in self._virtual_physical_map["couplings"].values()  # type: ignore
        ]  # type: ignore

    @property
    def virtual_physical_qubits(self) -> dict:
        """
        Returns the virtual-to-physical mapping, e.g., {0: "Q05", 1: "Q07"}
        """
        # Return a shallow copy to avoid accidental modifications
        return self._virtual_physical_map["qubits"].copy()  # type: ignore

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
