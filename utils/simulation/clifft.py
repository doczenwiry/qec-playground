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

from datetime import datetime
import hashlib
from typing import Union, cast, Optional
import re

import clifft
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sinter
import time
from matplotlib.container import BarContainer

__all__ = ["sample"]

from library.circuitry import Circuitry


def _collect(
    program: clifft.Program,
    json_metadata: dict,
    strong_id: str,
    shots: int,
    max_errors: int,
    batch_shots: int,
    num_workers: int,
) -> sinter.TaskStats:
    assert len(set(program.noise_site_probabilities)) == 1
    total, discards, errors = 0, 0, 0
    start = time.monotonic()
    while total < shots and errors < max_errors:
        # seed=None: fresh randomness per batch, a fixed seed would repeat shots
        result = clifft.sample_survivors(
            program, min(batch_shots, shots - total), threads=num_workers
        )
        total += result.total_shots
        discards += result.discards
        errors += result.logical_errors
    return sinter.TaskStats(
        strong_id=strong_id,
        decoder="clifft-postselection",
        json_metadata=json_metadata,
        shots=total,
        errors=errors,
        discards=discards,
        seconds=time.monotonic() - start,
    )


# Thanks, Claude.AI (November 2026)
def simulate(
    scenarios: dict[str, Circuitry],
    label: Optional[str] = None,
    postselection: bool = False,
    shots=1e6,
    minimal_noise=-6,
    points: int = 10,
    num_workers: int = 4,
    max_errors: int = 5000,
    batch_shots: int = 100_000,
    directory: str = "simulations",
    exclude: Optional[list[str]] = None,
    proxy_replacements: Optional[dict[str, str]] = None,
) -> list[str]:
    """Same sweep and CSV layout as simulation.stim.simulate, so stim.plot reads the output.

    Clifft has no decoder: shots failing a postselected detector are discarded and
    every observable flip on a surviving shot counts as a logical error.
    """
    if exclude is None:
        exclude = []
    if proxy_replacements is None:
        proxy_replacements = {}

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot_count = f".shots={re.sub(r'e\+?(-?)0*(\d)', r'e\1\2', f'{shots:.0e}')}"
    filename_prefix = f"{directory}/simulation-results-{timestamp}"

    paths = []
    for index, (scenario, circuitry) in enumerate(scenarios.items()):
        if scenario in exclude:
            continue
        group = []
        for per in np.logspace(-1, minimal_noise, num=points):
            json_metadata = {"scenario": scenario, "per": float(per)}
            strong_id = hashlib.sha256(
                f"{timestamp}|{scenario}|{per}".encode()
            ).hexdigest()
            stats = _collect(
                circuitry.as_clifft(
                    proxy_replacements,
                    per=float(per),
                    postselection=postselection,
                    deterministic=True,
                ),
                json_metadata,
                strong_id,
                int(shots),
                max_errors,
                batch_shots,
                num_workers,
            )
            print(
                f"{scenario} p={per:.2e}: {stats.errors} errors, "
                f"{stats.discards}/{stats.shots} discarded"
            )
            group.append(stats)

        scenario_label = (
            f".{label.lower()}.{index}" if label is not None else ""
        ) + f".{scenario.lower().replace(' ', '-')}"
        postselected = (
            ".postselected"
            if postselection and any(circuitry.postselection_mask)
            else ""
        )
        path = f"{filename_prefix}{shot_count}{scenario_label}{postselected}.csv"
        with open(path, "w", encoding="utf-8") as file:
            file.write(sinter.CSV_HEADER + "\n")
            file.writelines(stat.to_csv_line() + "\n" for stat in group)
        paths.append(path)

    return paths


SEED = 42


# Thanks, Claude.AI (September 2026)
def sample(
    scenarios: Union[Circuitry, dict[str, Circuitry]],
    postselection: bool = False,
    correction: bool = True,
    title: str = "Sampling results",
    label: str = "Scenario",
    shots=1e6,
    figsize: tuple[float, float] = (11, 5),
    fontsize: int = 12,
    proxy_replacements: Optional[dict[str, str]] = None,
):
    if isinstance(scenarios, Circuitry):
        scenarios = {"circuit": scenarios}

    if proxy_replacements is None:
        proxy_replacements = {}

    dataframes: list[pd.DataFrame] = []

    for scenario, circuit in scenarios.items():
        program = circuit.as_clifft(proxy_replacements)
        if postselection:
            results = clifft.sample_survivors(
                program, keep_records=True, shots=int(shots), seed=SEED
            )
        else:
            results = clifft.sample(program, shots=int(shots), seed=SEED)
        outcomes = (
            results.observables[:, 0] if correction else results.measurements[:, -1]
        )

        df = pd.DataFrame()
        df["Measured"] = outcomes.flatten()
        df[label] = scenario
        dataframes.append(df)

    dataframe = pd.concat(dataframes, ignore_index=True)
    dataframe["Measured"] = pd.Categorical(dataframe["Measured"], categories=[0, 1])
    n_categories = dataframe[label].nunique()

    plt.figure(figsize=figsize)
    ax = sns.histplot(
        data=dataframe,
        x=label,
        hue="Measured",
        hue_order=[0, 1],
        discrete=True,
        multiple="dodge",
        shrink=0.9,
        palette={1: "seagreen", 0: "indianred"},
    )
    ax.set_xlim(-0.5, n_categories - 0.5)
    ax.tick_params(axis="x", labelsize=fontsize)
    sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1))

    for container in ax.containers:
        ax.bar_label(
            cast(BarContainer, container),
            fmt=lambda x: f"{float(100.0 * x / shots):.2f}%",
            fontsize=fontsize,
        )

    plt.ylim(0, 1.075 * shots)
    plt.suptitle(title)
    plt.show()
