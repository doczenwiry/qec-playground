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
import sinter
import matplotlib.pyplot as plt
from tqec import NoiseModel

# Based on stim's getting started notebook
# cfr: https://github.com/quantumlib/Stim/blob/main/doc/getting_started.ipynb
def analyse_error_rates(
    scenarios, name ="circuit", shots= 1e6, minimal_noise = -6, points: int = 10
):
    tasks = [
        sinter.Task(
            circuit=NoiseModel.uniform_depolarizing(noise).noisy_circuit(scenarios[case]['circuit']),
            postselection_mask=np.packbits(scenarios[case].get('postselection')) if 'postselection' in scenarios[case] else None,
            json_metadata={'case': case, 'per': noise},
        )
        for case, noise in itertools.product(scenarios, np.logspace(-1, minimal_noise, num=points))
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
        x_func=lambda stats: stats.json_metadata['per'],
        group_func=lambda stats: stats.json_metadata['case'],
    )
    ax.set_ylim(1e-9, 1.5)
    ax.set_xlim(10**minimal_noise, 0.125)
    ax.loglog()
    ax.set_title(f"Analysis of {name}")
    ax.set_xlabel("Physical Error Rate")
    ax.set_ylabel("Logical Error Rate")
    ax.grid(which='major')
    ax.grid(which='minor')
    ax.legend(loc='lower right')
    fig.set_dpi(120)
