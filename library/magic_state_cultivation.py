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

from library.circuitry import Circuitry
from library.common import Pauli
from library.junction_patch import JunctionPatch
from library.qubit_array import QubitArray
from library.steane_code.patch import SteaneCodePatch
from library.surface_code.expanding_patch import ExpandingSurfaceCodePatch
from library.surface_code.patch import SurfaceCodePatch


class MagicStateCultivation:
    CORNERS: list[tuple[float, float]] = [
        (-0.5, -0.5),
        (+0.5, -0.5),
        (+0.5, +0.5),
        (-0.5, +0.5),
    ]
    EXPANDED_OPACITY: float = 0.125

    def __init__(
        self,
        injection: SteaneCodePatch.Injection,
        target_distance: int,
        anchor: tuple[int, int] = (1, 1),
        draw_neighbors: bool = False,
    ):
        if target_distance % 2 != 1:
            raise ValueError(
                f"MagicStateCultivation requires odd target distance. [req. {target_distance}]"
            )
        if target_distance < 7:
            raise ValueError(
                f"MagicStateCultivation requires target distance at least 7. [req. {target_distance}]"
            )

        self.qubits = QubitArray(dimensions=(target_distance + 6, target_distance + 6))
        ax, ay = anchor
        self.__anchor = anchor
        self.__target_distance = target_distance

        # Generate circuit up to and including preparation with S-injection
        self.circuitry = Circuitry(self.qubits, clifford=True)
        self.steane = SteaneCodePatch(
            self.qubits, (ax + target_distance - 6, ay + target_distance - 8), injection
        )
        self.source = SurfaceCodePatch(
            self.qubits,
            distance=5,
            anchor=(ax + target_distance - 5, ay + target_distance - 5),
        )
        self.__inactive_source = lambda location: (
            location[1] == ay + target_distance - 5.5
        )
        self.__junction = JunctionPatch(
            self.qubits, anchor=(ax + target_distance - 6, ay + target_distance - 6)
        )
        self.target = ExpandingSurfaceCodePatch(
            self.qubits, distance=5, anchor=self.__anchor, expansion=target_distance - 5
        )

        self.__draw_neighbors = draw_neighbors

    def get_polygons(self, opacity: float = 0.5):
        polygons = []

        # Surface Code Above
        ax, ay = self.__anchor
        sx, sy = (3, ay - 3)
        for ancilla in range(self.__target_distance):
            px, py = sx - 0.5, sy + 0.5
            x, z = int(ancilla % 2 == 1), int(ancilla % 2 == 0)
            polygon = [
                self.qubits[px + ancilla + dx, py + dy]
                for dx, dy in MagicStateCultivation.CORNERS
                if sx <= px + ancilla + dx
            ]
            polygons.append(
                f"POLYGON({x},0,{z},{opacity}) {' '.join(map(str, polygon))}"
            )
            if ancilla % 2 == 0 and ancilla > 0:
                polygon = [
                    self.qubits[px + ancilla + dx, py + dy]
                    for dx, dy in [(-0.5, +0.5), (+0.5, +0.5)]
                    if sx <= px + ancilla + dx
                ]
                polygons.append(
                    f"POLYGON(1,0,0,{opacity}) {' '.join(map(str, polygon))}"
                )

        # Surface Code Below
        sx, sy = (3, ay + self.__target_distance + 2)
        for ancilla in range(self.__target_distance):
            px, py = sx + 0.5, sy - 0.5
            x, z = int(ancilla % 2 == 1), int(ancilla % 2 == 0)
            polygon = [
                self.qubits[px + ancilla + dx, py + dy]
                for dx, dy in MagicStateCultivation.CORNERS
                if px + ancilla + dx < sx + self.__target_distance
            ]
            polygons.append(
                f"POLYGON({x},0,{z},{opacity}) {' '.join(map(str, polygon))}"
            )
            if ancilla % 2 == 0 and ancilla < self.__target_distance - 1:
                polygon = [
                    self.qubits[px + ancilla + dx, py + dy]
                    for dx, dy in [(-0.5, -0.5), (+0.5, -0.5)]
                    if sx <= px + ancilla + dx
                ]
                polygons.append(
                    f"POLYGON(1,0,0,{opacity}) {' '.join(map(str, polygon))}"
                )

        # Surface Code Left
        sx, sy = (ax - 3, ay)
        for ancilla in range(self.__target_distance):
            px, py = sx + 0.5, sy + 0.5
            x, z = int(ancilla % 2 == 0), int(ancilla % 2 == 1)
            polygon = [
                self.qubits[px + dx, py + ancilla + dy]
                for dx, dy in MagicStateCultivation.CORNERS
                if py + ancilla + dy < sy + self.__target_distance
            ]
            polygons.append(
                f"POLYGON({x},0,{z},{opacity}) {' '.join(map(str, polygon))}"
            )
            if ancilla % 2 == 0 and ancilla < self.__target_distance - 1:
                polygon = [
                    self.qubits[px + dx, py + ancilla + dy]
                    for dx, dy in [(+0.5, -0.5), (+0.5, +0.5)]
                    if sy <= py + ancilla + dy
                ]
                polygons.append(
                    f"POLYGON(0,0,1,{opacity}) {' '.join(map(str, polygon))}"
                )

        # Surface Code Right
        sx, sy = (ax + self.__target_distance + 1, ay)
        for ancilla in range(self.__target_distance):
            px, py = sx + 0.5, sy - 0.5
            x, z = int(ancilla % 2 == 0), int(ancilla % 2 == 1)
            polygon = [
                self.qubits[px + dx, py + ancilla + dy]
                for dx, dy in MagicStateCultivation.CORNERS
                if sy <= py + ancilla + dy
            ]
            polygons.append(
                f"POLYGON({x},0,{z},{opacity}) {' '.join(map(str, polygon))}"
            )
            if ancilla % 2 == 0 and 0 < ancilla:
                polygon = [
                    self.qubits[px + dx, py + ancilla + dy]
                    for dx, dy in [(-0.5, -0.5), (-0.5, +0.5)]
                    if sy <= py + ancilla + dy
                ]
                polygons.append(
                    f"POLYGON(0,0,1,{opacity}) {' '.join(map(str, polygon))}"
                )

        return polygons

    def append_preparation(self):
        self.circuitry.annotate_polygons(
            self.target.get_polygons(
                expanded=True, opacity=MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        self.circuitry.annotate_polygons(self.steane.get_polygons(initial=True))
        if self.__draw_neighbors:
            self.circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        self.steane.append_preparation(self.circuitry)

    def append_superdense_cycle(self, rnd: int):
        self.circuitry.annotate_polygons(
            self.target.get_polygons(
                expanded=True, opacity=MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        self.circuitry.annotate_polygons(self.steane.get_polygons())
        if self.__draw_neighbors:
            self.circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the superdense syndrome measurement code cycle (one round)
        self.steane.append_superdense_cycle(self.circuitry, prefix=f"SDC{rnd}")

    def append_cultivation(self):
        self.circuitry.annotate_polygons(
            self.target.get_polygons(
                expanded=True, opacity=MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        self.circuitry.annotate_polygons(self.steane.get_polygons())
        if self.__draw_neighbors:
            self.circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the cultivation stage with the Double-Check-S/T
        self.steane.append_cultivation(self.circuitry, prefix="CULT")

    def append_teleportation(self, rounds: int = 3):
        if rounds not in range(4):
            raise ValueError("Rounds of teleportation must be between 0 and 3.")

        # Append the three rounds of the teleportation stage
        self.circuitry.annotate_polygons(
            self.target.get_polygons(
                expanded=True, opacity=MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        self.circuitry.annotate_polygons(self.steane.get_polygons())
        self.circuitry.annotate_polygons(self.__junction.get_polygons())
        self.circuitry.annotate_polygons(
            self.source.get_polygons(self.__inactive_source)
        )
        if self.__draw_neighbors:
            self.circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        for rnd in range(rounds):
            for mmt in self.steane.TELEPORTATION_MOMENTS:
                self.steane.append_teleportation(
                    self.circuitry, moment=mmt, prefix=f"TPT{rnd}"
                )
                self.__junction.append_syndrome(
                    self.circuitry, moment=mmt, prefix=f"JCT{rnd}"
                )
                self.source.append_round(
                    self.circuitry,
                    moment=mmt,
                    prepare=Pauli.X if rnd == 0 else None,
                    prefix=f"SC{rnd}",
                    inactive=self.__inactive_source,
                )
                self.circuitry.append_tick()

        self.circuitry.annotate_polygons(
            self.target.get_polygons(
                expanded=True, opacity=MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        self.circuitry.annotate_polygons(
            self.steane.get_polygons(
                opacity=2.25 * MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        self.circuitry.annotate_polygons(self.source.get_polygons())
        if self.__draw_neighbors:
            self.circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        for mmt in self.steane.DESTRUCTION_MOMENTS:
            self.steane.append_destruction(self.circuitry, moment=mmt)
            self.source.append_round(self.circuitry, moment=mmt, prefix=f"SC{rounds}")
            self.circuitry.append_tick()

    def append_expansion(self):
        self.circuitry.annotate_polygons(self.target.get_polygons(expanded=True))
        if self.__draw_neighbors:
            self.circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the round of the expansion stage
        for mmt in self.target.MOMENTS:
            self.target.append_expansion(self.circuitry, moment=mmt, prefix="EXP")
            self.circuitry.append_tick()

    def annotate_detectors(self, sdc_rounds: int, tpt_rounds: int):
        self.steane.annotate_detectors(
            self.circuitry, sdc_rounds=sdc_rounds, tpt_rounds=tpt_rounds
        )
        self.__junction.annotate_detectors(self.circuitry, rounds=tpt_rounds)
        self.source.annotate_detectors(
            self.circuitry, rounds=tpt_rounds + 1, prepared=Pauli.X
        )
        self.target.annotate_detectors(
            self.circuitry, sc_rounds=tpt_rounds + 1, source=self.source
        )

    def append_observable(
        self, index: int, label: str, observable: dict[int, str], *extras: str
    ):
        self.circuitry.append_observable(index, label, observable, *extras)
