#   Copyright 2026 Seweryn Dynerowicz
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#          http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import itertools
import numpy as np
import stim
import sinter
import matplotlib.pyplot as plt
from tqec import NoiseModel

def noisify_phenomenological(circuit, noise = 0.001):
    noisy_circuit = stim.Circuit()

    for instruction in circuit.flattened():
        if instruction.name in ["M", "MX"]:
            noisy_circuit.append(instruction.name, instruction.targets_copy(), noise)
        elif instruction.name in ["R", "RX", "CX", "CZ", "QUBIT_COORDS", "TICK", "DETECTOR", "OBSERVABLE_INCLUDE"]:
            noisy_circuit.append(instruction)
        else:
            raise NotImplementedError(f"Incomplete noisification : {instruction.name}")

    noisy_circuit.compile_detector_sampler()
    noisy_circuit.compile_sampler()

    return noisy_circuit

# Based on stim's getting started notebook.
def analyse_error_rates(circuit, name = "circuit", shots= 1e6, minimal_noise = -6, points: int = 10):
    tasks = [
        sinter.Task(
            circuit=NoiseModel.uniform_depolarizing(noise).noisy_circuit(circuit),
            json_metadata={'d': d, 'p': noise},
        )
        for d, noise in itertools.product([5], np.logspace(-1, minimal_noise, num=points))
    ]

    collected_stats: list[sinter.TaskStats] = sinter.collect(
        num_workers=4,
        tasks=tasks,
        decoders=['pymatching'],
        max_shots=int(shots),
        max_errors=5000,
    )

    fig, ax = plt.subplots(1, 1)
    sinter.plot_error_rate(
        ax=ax,
        stats=collected_stats,
        x_func=lambda stats: stats.json_metadata['p'],
        group_func=lambda stats: stats.json_metadata['d'],
    )
    ax.set_ylim(1e-9, 1.5)
    ax.set_xlim(10**minimal_noise, 0.125)
    ax.loglog()
    ax.set_title(f"Analysis of {name}")
    ax.set_xlabel("Phyical Error Rate")
    ax.set_ylabel("Logical Error Rate per Shot")
    ax.grid(which='major')
    ax.grid(which='minor')
    ax.legend()
    fig.set_dpi(120)
