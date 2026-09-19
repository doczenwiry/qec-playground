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

import clifft
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sinter
import stim
from matplotlib.container import BarContainer
from tqec import NoiseModel
from tqec.utils.noise_model import NoiseRule

__all__ = ['sample']

from library.circuitry import Circuitry

SEED=42
# Thanks, Claude.AI (September 2026)
def sample(
    scenarios: Union[Circuitry, dict[str, Circuitry]], correction: bool = True,
    title: str = "Sampling results", label: str = "Scenario",
    shots=1e6, figsize: tuple[float, float] = (11, 5), fontsize: int = 12
):
    if isinstance(scenarios, Circuitry):
        scenarios = { 'circuit' : scenarios }

    dataframes: list[pd.DataFrame] = []

    for scenario, circuit in scenarios.items():
        results = clifft.sample(
            clifft.compile(str(circuit)), shots=int(shots), seed=SEED
        )
        outcomes = results.observables[:, 0] if correction else results.measurements[:, -1]

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