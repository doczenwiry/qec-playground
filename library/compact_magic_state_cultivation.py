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
from library.compact_junction_patch import JunctionPatch
from library.qubit_array import QubitArray
from library.steane_code.compact_patch import SteaneCodePatch
from library.surface_code.expansion import ExpansionSurgery
from library.surface_code.patch import SurfaceCodePatch


class MagicStateCultivation:
    CORNERS: list[tuple[float, float]] = [
        (-0.5, -0.5),
        (+0.5, -0.5),
        (+0.5, +0.5),
        (-0.5, +0.5),
    ]
    EXPANDED_OPACITY: float = 0.125

    NON_CLIFFORD_PROXY_REPLACEMENTS: dict[str, str] = {
        "proxy:T" : "T",
        "proxy:T_DAG" : "T_DAG",
    }

    def __init__(
        self,
        qubits: QubitArray,
        target: SurfaceCodePatch,
        draw_neighbors: bool = False,
    ):
        if target.distance % 2 != 1:
            raise ValueError(
                f"MagicStateCultivation requires odd target distance. [req. {target.distance}]"
            )
        if target.distance < 7:
            raise ValueError(
                f"MagicStateCultivation requires target distance at least 7. [req. {target.distance}]"
            )

        ax, ay = target.anchor
        self.qubits = qubits

        # Generate circuit up to and including preparation with S/T-injection
        self.steane = SteaneCodePatch(
            self.qubits, (ax + target.distance - 6, ay + target.distance - 8)
        )
        self.source = SurfaceCodePatch(
            self.qubits,
            distance=5,
            anchor=(ax + target.distance - 5, ay + target.distance - 5),
        )
        self.__inactive_source = lambda location: (
            location[1] == ay + target.distance - 5.5
        )
        self.__junction = JunctionPatch(
            self.qubits, anchor=(ax + target.distance - 6, ay + target.distance - 6)
        )

        self.target = target
        self.__expansion = ExpansionSurgery(self.qubits, self.source, self.target)

        self.__draw_neighbors = draw_neighbors

    def get_polygons(self, opacity: float = 0.5):
        polygons = []

        # Surface Code Above
        ax, ay = self.target.anchor
        sx, sy = (3, ay - 3)
        for ancilla in range(self.target.distance):
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
        sx, sy = (3, ay + self.target.distance + 2)
        for ancilla in range(self.target.distance):
            px, py = sx + 0.5, sy - 0.5
            x, z = int(ancilla % 2 == 1), int(ancilla % 2 == 0)
            polygon = [
                self.qubits[px + ancilla + dx, py + dy]
                for dx, dy in MagicStateCultivation.CORNERS
                if px + ancilla + dx < sx + self.target.distance
            ]
            polygons.append(
                f"POLYGON({x},0,{z},{opacity}) {' '.join(map(str, polygon))}"
            )
            if ancilla % 2 == 0 and ancilla < self.target.distance - 1:
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
        for ancilla in range(self.target.distance):
            px, py = sx + 0.5, sy + 0.5
            x, z = int(ancilla % 2 == 0), int(ancilla % 2 == 1)
            polygon = [
                self.qubits[px + dx, py + ancilla + dy]
                for dx, dy in MagicStateCultivation.CORNERS
                if py + ancilla + dy < sy + self.target.distance
            ]
            polygons.append(
                f"POLYGON({x},0,{z},{opacity}) {' '.join(map(str, polygon))}"
            )
            if ancilla % 2 == 0 and ancilla < self.target.distance - 1:
                polygon = [
                    self.qubits[px + dx, py + ancilla + dy]
                    for dx, dy in [(+0.5, -0.5), (+0.5, +0.5)]
                    if sy <= py + ancilla + dy
                ]
                polygons.append(
                    f"POLYGON(0,0,1,{opacity}) {' '.join(map(str, polygon))}"
                )

        # Surface Code Right
        sx, sy = (ax + self.target.distance + 1, ay)
        for ancilla in range(self.target.distance):
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

    def append_injection(self, circuitry: Circuitry):
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons(initial=True))
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        self.steane.append_injection(circuitry)

    def append_superdense_cycle(self, circuitry: Circuitry, prefix: str = "SDC"):
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons())
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the superdense syndrome measurement code cycle (one round)
        self.steane.append_superdense_cycle(circuitry, prefix=f"{prefix}")

    def append_doublecheck(self, circuitry: Circuitry):
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons(compact=False))
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the cultivation stage with the Double-Check-S/T
        self.steane.append_doublecheck(circuitry, prefix="STN:CULT")

    def append_teleportation(self, circuitry: Circuitry):
        # Append the first two rounds of the teleportation stage
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons(compact=False))
        circuitry.annotate_polygons(self.__junction.get_polygons())
        circuitry.annotate_polygons(self.source.get_polygons(self.__inactive_source))
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        for mmt in self.steane.TELEPORTATION_ROUND_ONE_MOMENTS:
            self.steane.append_teleportation_round_one(circuitry, moment=mmt, prefix=f"STN:TPT0")
            if 0 <= mmt <= 4:
                translated_mmt = mmt
            elif mmt == self.steane.TELEPORTATION_ROUND_ONE_MOMENTS[-1]:
                translated_mmt = 5
            else:
                translated_mmt = -1

            if translated_mmt != -1:
                self.__junction.append_syndrome(circuitry, moment=translated_mmt, prefix=f"JCT:TPT0")
                self.source.append_round_6steps(
                    circuitry,
                    moment=translated_mmt,
                    prepare=Pauli.X,
                    prefix=f"SRC:TPT0",
                    inactive=self.__inactive_source,
                )
            circuitry.append_tick()

        for mmt in self.steane.TELEPORTATION_ROUND_TWO_MOMENTS:
            self.steane.append_teleportation_round_two(circuitry, moment=mmt, prefix=f"STN:TPT1")
            if 0 <= mmt <= 4:
                translated_mmt = mmt
            elif mmt == self.steane.TELEPORTATION_ROUND_TWO_MOMENTS[-1]:
                translated_mmt = 5
            else:
                translated_mmt = -1

            if translated_mmt != -1:
                self.__junction.append_syndrome(circuitry, moment=translated_mmt, prefix=f"JCT:TPT1")
                self.source.append_round_6steps(
                    circuitry,
                    moment=translated_mmt,
                    prefix=f"SRC:TPT1",
                    inactive=self.__inactive_source,
                )
            circuitry.append_tick()

        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons(compact=False))
        circuitry.annotate_polygons(self.__junction.get_polygons(recovered_stabilizers=True))
        circuitry.annotate_polygons(self.source.get_polygons(self.__inactive_source))
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the third round of teleportation
        for mmt in self.steane.DESTRUCTION_MOMENTS:
            self.steane.append_destruction(circuitry, moment=mmt, prefix="STN:TPT2")
            self.__junction.append_syndrome(circuitry, moment=mmt, prefix=f"JCT:TPT2", recovered_stabilizers=True)
            self.source.append_round_6steps(circuitry, moment=mmt, prefix="SRC:TPT2", inactive=self.__inactive_source)
            circuitry.append_tick()

    def append_expansion(self, circuitry: Circuitry):
        circuitry.annotate_polygons(self.target.get_polygons())
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Number of memory experiment to fit a single end-to-end MSC attempt
        # memories = math.ceil(11 / self.target.distance)
        # Number of padding rounds required to line up the destructive measurements
        # padding = (memories * self.target.distance) - 11
        # rounds = self.target.distance + padding

        rounds = 3

        # Append the rounds of the expansion stage
        self.__expansion.append_expansion(circuitry, rounds=rounds)

        return rounds

    def critical_on_seam(self, stabilizer: str, location: tuple[float, float]) -> bool:
        sx, sy = self.source.anchor
        j, i = location[0] - sx - 0.5, location[1] - sy - 0.5
        return stabilizer == "X" and i >= 0 and j >= 0 and i+j <= self.source.distance // 2 and (i+j) % 2 == 1

    def annotate_detectors(
        self, circuitry: Circuitry, sdc_rounds: int, exp_rounds: int
    ):
        self.steane.annotate_detectors(
            circuitry, sdc_rounds=sdc_rounds
        )

        # Annotate the TELEPORTATION destructive detectors
        # The X_{0126ab} detector.
        circuitry.annotate_detector(
            *(f"STN:TPT2:X{mx}" for mx in [0, 1, 2, 6]),
            f"JCT:TPT2:X0",
            postselected=True,
        )

        # The X_{2456} detector
        circuitry.annotate_detector(
            *(f"STN:TPT2:X{mx}" for mx in [2, 4, 5, 6]),
            postselected=True,
        )

        # The X_{0234} detector
        circuitry.annotate_detector(
            *(f"STN:TPT2:X{mx}" for mx in [0, 2, 3, 4]), postselected=True
        )

        self.__junction.annotate_detectors(
            circuitry, rounds=3, prefix="JCT:TPT", postselected=True
        )
        self.source.annotate_detectors(
            circuitry, rounds=3, prepared=Pauli.X, prefix="SRC:TPT",
            postselected_stabilizer=self.critical_on_seam
        )

        if exp_rounds > 0:
            tx, ty = self.target.anchor

            for ql, (qz, qti) in self.target.qubits["Z"].items():
                qsi = self.source.get_qubit_index("Z", qz)
                if qsi == -1:
                    px, py = ql
                    if px - tx < py - ty:
                        circuitry.annotate_detector(f"TGT:EXP:R0:Z{qti}")
                else:
                    circuitry.annotate_detector(f"TGT:EXP:R0:Z{qti}", f"SRC:TPT2:Z{qsi}")

            for ql, (qx, qti) in self.target.qubits["X"].items():
                qsi = self.source.get_qubit_index("X", qx)
                if qsi == -1:
                    px, py = ql
                    if px - tx > py - ty:
                        circuitry.annotate_detector(f"TGT:EXP:R0:X{qti}")
                else:
                    circuitry.annotate_detector(
                        f"TGT:EXP:R0:X{qti}", f"SRC:TPT2:X{qsi}",
                        postselected=self.critical_on_seam("X", ql)
                    )

            self.target.annotate_detectors(
                circuitry, rounds=self.target.distance + exp_rounds, prefix="TGT:EXP:R",
                postselected_stabilizer=self.critical_on_seam
            )
