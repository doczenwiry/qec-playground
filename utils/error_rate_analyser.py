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
from typing import Union, Optional

import matplotlib.pyplot as plt
import numpy as np
import sinter
import stim
from tqec import NoiseModel

from library.circuitry import Circuitry


# Based on stim's getting started notebook
# cfr: https://github.com/quantumlib/Stim/blob/main/doc/getting_started.ipynb
def simulate(
    scenarios: Union[Circuitry, dict[str, Circuitry]], title ="circuit",
    postselection: bool = False, shots= 1e6, minimal_noise = -6, points: int = 10,
    num_workers: int = 4, max_errors: int = 5000, figsize: tuple[float,float] = (11,5),
    filename: Optional[str] = None,
):
    if isinstance(scenarios, Circuitry):
        scenarios = { 'circuit' : scenarios }
    tasks = [
        sinter.Task(
            circuit=NoiseModel.uniform_depolarizing(noise).noisy_circuit(circuitry.as_stim),
            postselection_mask=np.packbits(np.ones(circuitry.num_detectors, dtype=bool)) if postselection else None,
            json_metadata={'case': case, 'per': noise},
        )
        for (case, circuitry), noise in itertools.product(
            scenarios.items(), np.logspace(-1, minimal_noise, num=points)
        )
    ]

    collected_stats: list[sinter.TaskStats] = sinter.collect(
        num_workers=num_workers,
        tasks=tasks,
        decoders=['pymatching'],
        max_shots=int(shots),
        max_errors=max_errors,
        print_progress=True,
        save_resume_filepath=filename + ".results.csv" if filename else None,
    )

    fig, axes = plt.subplots(1, 2 if postselection else 1, figsize=figsize)
    error_rates = axes[0] if postselection else axes
    sinter.plot_error_rate(
        ax=error_rates,
        stats=collected_stats,
        x_func=lambda stats: stats.json_metadata['per'],
        group_func=lambda stats: stats.json_metadata['case'],
    )
    error_rates.set_ylim(1e-9, 1.5)
    error_rates.set_xlim(10**minimal_noise, 0.125)
    error_rates.loglog()
    error_rates.set_title(f"Error rates")
    error_rates.set_xlabel("Physical Error Rate")
    error_rates.set_ylabel("Logical Error Rate")
    error_rates.grid(which='major')
    error_rates.grid(which='minor')
    error_rates.legend(loc='lower right')
    fig.set_dpi(120)

    if postselection:
        discard_rates = axes[1]
        sinter.plot_discard_rate(
            ax=discard_rates,
            stats=collected_stats,
            group_func=lambda stat: stat.json_metadata['case'],
            x_func=lambda stat: stat.json_metadata['per'],
        )
        discard_rates.set_title(f"Discard rates")
        discard_rates.set_xlabel('Physical Error Rate')
        discard_rates.set_ylabel('Discard Rate')
        discard_rates.set_ylim(1e-9, 1.5)
        discard_rates.set_xlim(10**minimal_noise, 0.125)
        discard_rates.grid(which='major')
        discard_rates.grid(which='minor')
        discard_rates.loglog()
        discard_rates.legend(loc='lower right')
        fig.set_dpi(120)

    fig.suptitle(title)
    plt.tight_layout()