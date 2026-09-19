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
from typing import Union, Optional, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sinter
import stim
from matplotlib.container import BarContainer

from library.circuitry import Circuitry
from utils.simulation.noise import make_noisy_circuit

__all__ = ['simulate', 'sample']

# Based on stim's getting started notebook
# cfr: https://github.com/quantumlib/Stim/blob/main/doc/getting_started.ipynb
def simulate(
    scenarios: Union[stim.Circuit, dict[str, stim.Circuit]], title: str ="Simulation results", label: str = "",
    postselection: bool = False, shots= 1e6, minimal_noise = -6, points: int = 10,
    num_workers: int = 4, max_errors: int = 5000, figsize: tuple[float,float] = (11,5),
    filename: Optional[str] = None,
):
    if isinstance(scenarios, stim.Circuit):
        scenarios = { 'circuit' : scenarios }
    tasks = [
        sinter.Task(
            circuit=make_noisy_circuit(circuit, physical_error_rate),
            postselection_mask=np.packbits(np.ones(circuit.num_detectors, dtype=bool)) if postselection else None,
            json_metadata={'scenario': scenario, 'per': physical_error_rate},
        )
        for (scenario, circuit), physical_error_rate in itertools.product(
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
    labels = {
        scenario : f"{label} {index} - {scenario}"
        for index, scenario in enumerate(scenarios)
    }
    error_rates = axes[0] if postselection else axes
    sinter.plot_error_rate(
        ax=error_rates,
        stats=collected_stats,
        x_func=lambda stats: stats.json_metadata['per'],
        group_func=lambda stats: labels.get(stats.json_metadata['scenario']),
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
            x_func=lambda stat: stat.json_metadata['per'],
            group_func=lambda stats: labels.get(stats.json_metadata['scenario']),
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

SEED=42
# Thanks, Claude.AI (September 2026)
def sample(
    scenarios: Union[stim.Circuit, dict[str, stim.Circuit]], correction: bool = True,
    title: str = "Sampling results", label: str = "Scenario",
    shots=1e6, figsize: tuple[float, float] = (11, 5), fontsize: int = 12
):
    if isinstance(scenarios, stim.Circuit):
        scenarios = { 'circuit' : scenarios }

    dataframes: list[pd.DataFrame] = []

    for scenario, circuit in scenarios.items():
        # Sample but only keep the final corrected measurement (i.e. OBSERVABLE)
        if correction:
            sampler = circuit.compile_detector_sampler(seed=SEED)
            _, outcomes = sampler.sample(shots=int(shots), separate_observables=True)
            outcomes = outcomes.astype(int)[:, 0]
        else:
            outcomes = circuit.compile_sampler().sample(shots=int(shots)).astype(int)[:, -1]

        df = pd.DataFrame()
        df["Measured"] = outcomes.flatten()
        df[label] = scenario
        dataframes.append(df)

    dataframe = pd.concat(dataframes, ignore_index=True)
    dataframe["Measured"] = pd.Categorical(dataframe["Measured"], categories=[0, 1])
    n_categories = dataframe[label].nunique()

    plt.figure(figsize=figsize)
    ax = sns.histplot(
        data=dataframe, x=label, hue="Measured", hue_order=[0, 1],
        discrete=True, multiple="dodge", shrink=0.9, palette={1: "seagreen", 0: "indianred"},
    )
    ax.set_xlim(-0.5, n_categories - 0.5)
    ax.tick_params(axis='x', labelsize=fontsize)
    sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1))

    for container in ax.containers:
        ax.bar_label(cast(BarContainer, container), fmt=lambda x: f"{float(100.0 * x / shots):.2f}%", fontsize=fontsize)

    plt.ylim(0, 1.075 * shots)
    plt.suptitle(title)
    plt.show()