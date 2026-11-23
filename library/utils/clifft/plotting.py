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

from typing import Optional, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas

def plot_logical_error_rates(
    results_ler: dict[str, pandas.DataFrame],
    results_cer: dict[str, pandas.DataFrame],
    label: Optional[str] = None,
    noise_levels: Optional[np.ndarray] = None,
    estimate_distance: bool = True,
):
    if noise_levels is None:
        noise_levels = np.logspace(-7, -2, num=11)

    fig, ler_ax = plt.subplots(nrows=1, ncols=1, figsize=(14, 5.5))

    scenario_indices = {
        scenario: index for index, scenario in enumerate(results_ler.keys())
    }

    for scenario, ler in results_ler.items():
        index = scenario_indices[scenario]
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

    if estimate_distance:
        colors = {
            line.get_label(): line.get_color() for line in ler_ax.get_lines()
        }
        for scenario, (slope, error, (p0, r0), (p1, r1)) in _estimate_slopes(results_ler, results_cer).items():
            index = scenario_indices[scenario]
            text = (
                rf"$\approx p^{{{slope:.1f}}}$" if np.isnan(error)
                else rf"$\approx p^{{{slope:.1f} \pm {error:.1f}}}$"
            )
            identifier = (f"{label} {index} - " if label is not None else "") + scenario
            ler_ax.annotate(
                text,
                xy=(np.sqrt(p0 * p1), np.sqrt(r0 * r1)),
                xytext=(6, -10),
                textcoords="offset points",
                fontsize=8,
                color=colors.get(identifier, "black"),
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

def plot_stratum_data(
    results: dict[str, pandas.DataFrame],
    label: Optional[str] = None,
):
    fig, axes = plt.subplots(nrows=1, ncols=len(results), figsize=(14, 5.5))
    if len(results) == 1:
        axes = [axes]

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

        identifier = (f"{label} {index} - " if label is not None else "") + scenario
        cer_ax.set_title(identifier)
        cer_ax.grid(axis="y", alpha=0.3)

        counts = cer["logical_errors"]
        cnt_ax = cer_ax.twinx()
        cnt_ax.bar(cer.index, counts.where(counts > 0), color=color, alpha=0.1, width=0.666)
        cnt_ax.axhline(1e2, color="red", linestyle="--", alpha=0.4)
        cnt_ax.set_yscale("log")
        cnt_ax.set_ylabel("Logical errors witnessed")
        cnt_ax.set_ylim(bottom = 0.8, top = max(1.2 * counts.max(), 1e3))

    fig.suptitle("Conditional Error Rates")
    fig.tight_layout()
    plt.show(fig)

def _estimate_slopes(
    ler_curves: dict[str, pandas.DataFrame],
    cer_distributions: dict[str, pandas.DataFrame],
    min_errors: int = 50,
    max_per: float = 1e-3,
) -> dict[str, tuple[float, float, tuple[float, float], tuple[float, float]]]:
    """Slope of log(LER) vs log(PER) over points with PER <= max_per and enough logical errors found."""
    slopes: dict[str, tuple[float, float, tuple[float, float], tuple[float, float]]] = {}

    for scenario, ler in ler_curves.items():
        if cer_distributions[scenario]["logical_errors"].sum() < min_errors:
            continue

        physical_error_rates = ler["physical_error_rate"]
        points = physical_error_rates <= max_per
        count = points.sum()

        if count < 2:
            continue

        x = np.log10(ler.loc[points, "physical_error_rate"])
        y = np.log10(ler.loc[points, "logical_error_rate"])
        if count >= 3:
            coefficients, covariance = np.polyfit(x, y, 1, cov=True)
            error = float(np.sqrt(covariance[0, 0]))
        else:
            coefficients, error = np.polyfit(x, y, 1), float("nan")

        # Thanks, Claude.AI (November 2026)
        slope, intercept = float(coefficients[0]), float(coefficients[1])
        start = (10**float(x.iloc[0]), 10 ** (intercept + slope * float(x.iloc[0])))
        final = (10 ** float(y.iloc[-1]), 10 ** (intercept + slope * float(y.iloc[-1])))

        slopes[scenario] = slope, error, start, final

    return slopes