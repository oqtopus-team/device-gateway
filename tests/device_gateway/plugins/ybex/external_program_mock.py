import json
import math
import random
import sys
from collections import Counter


def main():
    if len(sys.argv) != 3:
        print("Usage: external_program_mock.py <shots> <angle(rad)>")
        sys.exit(1)

    shots = int(sys.argv[1])
    angle = float(sys.argv[2])

    # After applying RX(θ) to |0>, the result is cos(θ/2)|0> - i·sin(θ/2)|1>
    prob_0 = math.cos(angle / 2) ** 2

    # Simulation (sampling with random numbers)
    results = []
    for _ in range(shots):
        r = random.random()
        results.append("0" if r < prob_0 else "1")

    # Count the measurement results
    counts = Counter(results)
    print(json.dumps(dict(counts)))


if __name__ == "__main__":
    main()
