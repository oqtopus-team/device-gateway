from abc import ABCMeta

from qiskit import QuantumCircuit as QiskitQuantumCircuit


class BaseCircuit(metaclass=ABCMeta):
    """
    Circuit class is responsible for building and compiling QASM 3 programs.
    It holds the gate-level operations and returns a compiled circuit,
    which is then passed to the backend for execution.
    """

    def __init__(self):
        # Store instructions as a list of tuples, e.g., ("cnot", control, target)
        self.program = None

    def _cx(self, circuit, control: str, target: str):
        """
        Add a CX gate instruction to the circuit.
        Implement this method in the derived class.
        """
        raise NotImplementedError("This method is not implemented")

    def _sx(self, circuit, target: str):
        """
        Add an SX gate instruction to the circuit.
        Implement this method in the derived class.
        """
        raise NotImplementedError("This method is not implemented")

    def _x(self, circuit, target: str):
        """
        Add an X gate instruction to the circuit.
        Implement this method in the derived class.
        """
        raise NotImplementedError("This method is not implemented")

    def _rz(self, circuit, target: str, angle: float):
        """
        Add an RZ gate instruction to the circuit.
        Implement this method in the derived class.
        """
        raise NotImplementedError("This method is not implemented")

    def compile(self, qc: QiskitQuantumCircuit):
        """
        Compile the circuit by performing validation or optimization if necessary.
        Returns the compiled circuit, which in this simple example is just the list of instructions.
        Implement this method in the derived class.
        """
        raise NotImplementedError("This method is not implemented")
