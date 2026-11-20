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
from typing import Optional

import numpy as np
import sinter
from matplotlib import pyplot as plt


def plot(
    filepaths: list[str],
    title: str = "Simulation results",
    minimal_noise: int = -6,
    noise_levels: Optional[np.ndarray] = None,
    figsize: tuple[float, float] = (11, 5),
    postselection: bool = False,
    estimate_distance: bool = True,
):
    if noise_levels is None:
        noise_levels = np.logspace(-7, -2, num=11)

    collected_stats = []
    labels = {}
    for filepath in filepaths:
        stats = sinter.read_stats_from_csv_files(filepath)
        for stat in stats:
            label = stat.json_metadata["label"] if "label" in stat.json_metadata else ""
            scenario = stat.json_metadata["scenario"]
            labels[scenario] = f"{label} - {scenario}" if label != "" else scenario
        collected_stats.extend(stats)

    fig, axes = plt.subplots(1, 2 if postselection else 1, figsize=figsize)
    error_rates = axes[0] if postselection else axes
    sinter.plot_error_rate(
        ax=error_rates,
        stats=collected_stats,
        x_func=lambda stats: stats.json_metadata["per"],
        group_func=lambda stats: labels.get(stats.json_metadata["scenario"]),
    )

    if estimate_distance:
        colors = {
            line.get_label(): line.get_color() for line in error_rates.get_lines()
        }
        for scenario, (slope, error, (p0, r0), (p1, r1)) in estimate_slopes(
            collected_stats
        ).items():
            text = (
                rf"$\approx p^{{{slope:.1f}}}$"
                if np.isnan(error)
                else rf"$\approx p^{{{slope:.1f} \pm {error:.1f}}}$"
            )
            error_rates.annotate(
                text,
                xy=(np.sqrt(p0 * p1), np.sqrt(r0 * r1)),
                xytext=(6, -10),
                textcoords="offset points",
                fontsize=8,
                color=colors.get(labels[scenario], "black"),
            )

    error_rates.set_ylim(1e-12, 1.5)
    error_rates.set_xlim(noise_levels.min(), 0.125)
    error_rates.loglog()
    error_rates.set_title("Error rates")
    error_rates.set_xlabel("Physical Error Rate")
    error_rates.set_ylabel("Logical Error Rate")
    error_rates.grid(which="major")
    error_rates.grid(which="minor")
    error_rates.legend(loc="lower right")
    fig.set_dpi(120)

    if postselection:
        discard_rates = axes[1]
        sinter.plot_discard_rate(
            ax=discard_rates,
            stats=collected_stats,
            x_func=lambda stat: stat.json_metadata["per"],
            group_func=lambda stats: labels.get(stats.json_metadata["scenario"]),
        )
        discard_rates.set_title("Discard rates")
        discard_rates.set_xlabel("Physical Error Rate")
        discard_rates.set_ylabel("Discard Rate")
        discard_rates.set_ylim(1e-9, 1.5)
        discard_rates.set_xlim(10**minimal_noise, 0.125)
        discard_rates.grid(which="major")
        discard_rates.grid(which="minor")
        discard_rates.loglog()
        discard_rates.legend(loc="lower right")
        fig.set_dpi(120)

    fig.suptitle(title)
    plt.tight_layout()


# Thanks, Claude.AI
def estimate_slopes(
    stats: list[sinter.TaskStats],
    min_errors: int = 50,
    max_per: float = 1e-3,
) -> dict[str, tuple[float, float, tuple[float, float], tuple[float, float]]]:
    """Slope of log(p_L) vs log(p) over points with p <= max_per and enough statistics."""
    points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for stat in stats:
        kept = stat.shots - stat.discards
        rate = stat.errors / kept if kept > 0 else 1.0
        per = stat.json_metadata["per"]
        if stat.errors >= min_errors and per <= max_per:
            points[stat.json_metadata["scenario"]].append((per, rate))

    slopes = {}
    for scenario, pts in points.items():
        pts.sort()
        if len(pts) >= 2:
            x, y = np.log10(np.array(pts).T)
            if len(pts) >= 3:
                coefficients, cov = np.polyfit(x, y, 1, cov=True)
                error = float(np.sqrt(cov[0, 0]))
            else:
                coefficients, error = np.polyfit(x, y, 1), float("nan")
            slopes[scenario] = (float(coefficients[0]), error, pts[0], pts[-1])
    return slopes
