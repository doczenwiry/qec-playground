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
from collections import defaultdict
from typing import Optional, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas

def plot_logical_error_rates(
    results: dict[str, pandas.DataFrame],
    label: Optional[str] = None,
    noise_levels: Optional[np.ndarray] = None,
):
    if noise_levels is None:
        noise_levels = np.logspace(-7, -2, num=11)

    fig, ler_ax = plt.subplots(nrows=1, ncols=1, figsize=(14, 5.5))

    for index, (scenario, ler) in enumerate(results.items()):
        color = f"C{index}"
        identifier = (f"{label} {index} - " if label is not None else "") + scenario
        ler_ax.plot(
            ler["physical_error_rate"], ler["logical_error_rate"],
            label=identifier, color=color, zorder=3, marker="o"
        )

        minimum = np.maximum(
            ler["logical_error_rate"] - ler["logical_error_rate_wald_ci"],
            ler["logical_error_rate"] * 1e-3
        )
        maximum = ler["logical_error_rate"] + ler["logical_error_rate_wald_ci"]
        ler_ax.fill_between(
            ler["physical_error_rate"], minimum, maximum,
            color=color, zorder=2, alpha=0.2
        )

    ler_ax.set_xlim(noise_levels.min(), noise_levels.max() + 0.125)
    ler_ax.set_ylim(1e-19, 1.5)

    ler_ax.loglog()
    ler_ax.grid(which="major", color="#000000", alpha=0.3)
    ler_ax.grid(which="minor", color="#DDDDDD", alpha=0.5)
    ler_ax.set_xlabel("Physical error rate")
    ler_ax.set_ylabel("Logical error rate")
    ler_ax.legend(loc="lower right")
    ler_ax.set_title(f"Postselected Error rates")

    fig.set_dpi(120)
    fig.tight_layout()
    plt.show(fig)

def plot_conditional_error_rates(
    results: dict[str, pandas.DataFrame],
):
    fig, axes = plt.subplots(nrows=1, ncols=len(results), figsize=(14, 5.5))

    for index, (scenario, cer) in enumerate(results.items()):
        cer_ax = axes[index]
        color = f"C{index}"
        cer_ax.errorbar(
            cer.index, cer["logical_error_rate"], yerr=cer["logical_error_rate_wald_ci"],
            color=color, zorder=4, fmt="o-", capsize=3,
        )

        cer_ax.set_xticks(cer.index.astype(int))
        cer_ax.set_xlabel("Number of faults [k]")
        cer_ax.set_ylabel("Logical error rate")
        cer_ax.tick_params(axis="y")

        cer_ax.set_title(f"{scenario} - Conditional Error Rate")
        cer_ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    plt.show(fig)
