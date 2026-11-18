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
import os
from datetime import datetime
import hashlib
from typing import Union, cast, Optional
import re

import clifft
import itertools
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sinter
import time
from matplotlib.container import BarContainer

__all__ = ["sample"]

from library.circuitry import Circuitry


SEED = 42


def _stratified_mc_sampling(
    program: clifft.Program,
    shots: int,
    max_errors: int,
    batch_shots: int,
    workers: int,
) -> tuple[int, int, int]:
    assert len(set(program.noise_site_probabilities)) == 1

    total, discards, errors = 0, 0, 0

    strata: list[float] = []
    k: int
    weight: float
    for k, weight in itertools.product([], []):
        result = clifft.sample_k(program, shots=shots, k=k, seed=SEED + k)
        print(f"k={k} [w:{weight}] : {result.measurements[:, 0]}")
        conditional_one_rate = result.measurements[:, 0].mean()
        strata.append(weight * conditional_one_rate)

        # Ensure that the sampling produced valid results.
        assert result.total_shots is not None
        assert result.discards is not None
        assert result.logical_errors is not None

        # Update the counters
        total += result.total_shots
        discards += result.discards
        errors += result.logical_errors
    return total, errors, discards


# Based on Clifft's documentation about Importance Sampling
# cfr. https://unitaryfoundation.github.io/clifft/stable/guide/importance-sampling/
# cfr. https://unitaryfoundation.github.io/clifft/stable/guide/importance-sampling-tutorial/
def simulate(
    scenarios: dict[str, Circuitry],
    label: Optional[str] = None,
    postselection: bool = False,
    shots=1e6,
    noise_levels: Optional[np.ndarray] = None,
    workers: Optional[int] = None,
    max_errors: int = 5000,
    batch_shots: int = 100_000,
    directory: str = "simulations",
    exclude: Optional[list[str]] = None,
    proxy_replacements: Optional[dict[str, str]] = None,
) -> list[str]:
    """Computes the PER/LER curves using Stratified Monte Carlo Sampling."""
    if exclude is None:
        exclude = []
    if proxy_replacements is None:
        proxy_replacements = {}

    if workers is None:
        workers = (os.process_cpu_count() or 2) - 1

    if noise_levels is None:
        noise_levels = np.logspace(-6, -1, num=11)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot_count = f".shots={re.sub(r'e\+?(-?)0*(\d)', r'e\1\2', f'{shots:.0e}')}"
    filename_prefix = f"{directory}/simulation-results-{timestamp}"

    filepaths = []
    for index, (scenario, circuitry) in enumerate(scenarios.items()):
        if scenario in exclude:
            continue

        # Collect the results across all noise levels
        results = []
        for per in noise_levels:
            json_metadata = {"scenario": scenario, "per": float(per)}
            strong_id = hashlib.sha256(
                f"{timestamp}|{scenario}|{per}".encode()
            ).hexdigest()

            program = circuitry.as_clifft(
                proxy_replacements,
                per=float(per),
                postselection=postselection,
                deterministic=True,
            )

            # Perform the Stratified Monte Carlo Sampling.
            start = time.monotonic()
            total, errors, discards = _stratified_mc_sampling(
                program,
                int(shots),
                max_errors,
                batch_shots,
                workers,
            )
            final = time.monotonic()

            print(
                f"{scenario} p={per:.2e}: {errors} errors, {discards}/{shots} discarded."
            )

            results.append(
                sinter.TaskStats(
                    strong_id=strong_id,
                    decoder="clifft-postselection",
                    json_metadata=json_metadata,
                    shots=total,
                    errors=errors,
                    discards=discards,
                    seconds=final - start,
                )
            )

        scenario_label = f".{label.lower()}.{index}" if label is not None else ""
        scenario_name = f".{scenario.lower().replace(' ', '-')}"
        postselected = (
            ".postselected"
            if postselection and any(circuitry.postselection_mask)
            else ""
        )
        path = f"{filename_prefix}{shot_count}{scenario_label}{scenario_name}{postselected}.csv"
        with open(path, "w", encoding="utf-8") as file:
            file.write(sinter.CSV_HEADER + "\n")
            file.writelines(statistics.to_csv_line() + "\n" for statistics in results)
        filepaths.append(path)

    return filepaths


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
