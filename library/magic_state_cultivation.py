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

    def __init__(
        self,
        qubits: QubitArray,
        target: SurfaceCodePatch,
        injection: SteaneCodePatch.Injection,
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

        # Generate circuit up to and including preparation with S-injection
        self.steane = SteaneCodePatch(
            self.qubits, (ax + target.distance - 6, ay + target.distance - 8), injection
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

    def append_preparation(self, circuitry: Circuitry):
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons(initial=True))
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        self.steane.append_preparation(circuitry)

    def append_superdense_cycle(self, circuitry: Circuitry, rnd: int):
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons())
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the superdense syndrome measurement code cycle (one round)
        self.steane.append_superdense_cycle(circuitry, prefix=f"STN:SDC{rnd}")

    def append_cultivation(self, circuitry: Circuitry):
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons())
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the cultivation stage with the Double-Check-S/T
        self.steane.append_cultivation(circuitry, prefix="STN:CULT")

    def append_teleportation(self, circuitry: Circuitry, rounds: int = 3):
        if rounds not in range(4):
            raise ValueError("Rounds of teleportation must be between 0 and 3.")

        # Append the three rounds of the teleportation stage
        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(self.steane.get_polygons())
        circuitry.annotate_polygons(self.__junction.get_polygons())
        circuitry.annotate_polygons(self.source.get_polygons(self.__inactive_source))
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # TODO: synchronise the MEASUREMENTS in Steane & SurfaceCode
        for rnd in range(rounds):
            for mmt in self.steane.TELEPORTATION_MOMENTS:
                self.steane.append_teleportation(
                    circuitry, moment=mmt, prefix=f"STN:TPT{rnd}"
                )
                self.__junction.append_syndrome(
                    circuitry, moment=mmt, prefix=f"JCT{rnd}"
                )
                self.source.append_round(
                    circuitry,
                    moment=mmt,
                    prepare=Pauli.X if rnd == 0 else None,
                    prefix=f"SRC:R{rnd}",
                    inactive=self.__inactive_source,
                )
                circuitry.append_tick()

        circuitry.annotate_polygons(
            self.target.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
        )
        circuitry.annotate_polygons(
            self.steane.get_polygons(
                opacity=2.25 * MagicStateCultivation.EXPANDED_OPACITY
            )
        )
        circuitry.annotate_polygons(self.source.get_polygons())
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        for mmt in self.steane.DESTRUCTION_MOMENTS:
            self.steane.append_destruction(circuitry, moment=mmt)
            self.source.append_round(circuitry, moment=mmt, prefix="SRC:REC")
            circuitry.append_tick()

    def append_expansion(self, circuitry: Circuitry):
        circuitry.annotate_polygons(self.target.get_polygons())
        if self.__draw_neighbors:
            circuitry.annotate_polygons(
                self.get_polygons(opacity=MagicStateCultivation.EXPANDED_OPACITY)
            )

        # Append the rounds of the expansion stage
        self.__expansion.append_expansion(circuitry)

    def annotate_detectors(
        self, circuitry: Circuitry, sdc_rounds: int, tpt_rounds: int
    ):
        self.steane.annotate_detectors(
            circuitry, sdc_rounds=sdc_rounds, tpt_rounds=tpt_rounds
        )

        # Annotate the TELEPORTATION destructive detectors
        # The X_{0126ab} detector.
        last = sdc_rounds - 1
        circuitry.annotate_detector(
            f"STN:SDC{last}:XG",
            "STN:TPT0:XG",
            "STN:TPT0:XB",
            "STN:TPT1:XG",
            "STN:TPT1:XB",
            "STN:TPT2:XG",
            "STN:TPT2:XB",
            "STN:DST:X0",
            "STN:DST:X1",
            "STN:DST:X2",
            "STN:DST:X6",
            "SRC:REC:X0",
            postselected=True,
        )
        # The X_{2456} detector
        circuitry.annotate_detector(
            "STN:TPT2:XG",
            "STN:TPT2:XR",
            "STN:DST:X2",
            "STN:DST:X4",
            "STN:DST:X5",
            "STN:DST:X6",
            postselected=True,
        )
        # The X_{0234} detector
        circuitry.annotate_detector(
            "STN:DST:X0", "STN:DST:X2", "STN:DST:X3", "STN:DST:X4", postselected=True
        )

        self.__junction.annotate_detectors(circuitry, rounds=tpt_rounds)
        self.source.annotate_detectors(
            circuitry, rounds=tpt_rounds + 1, prepared=Pauli.X, prefix="SRC"
        )

        for ql, (qx, qi) in self.source.qubits["X"].items():
            if qi < 2:
                continue
            circuitry.annotate_detector(f"SRC:REC:X{qi}", f"SRC:R{last}:X{qi}")

        for ql, (qz, qi) in self.source.qubits["Z"].items():
            circuitry.annotate_detector(f"SRC:REC:Z{qi}", f"SRC:R{last}:Z{qi}")

        tx, ty = self.target.anchor

        for ql, (qz, qti) in self.target.qubits["Z"].items():
            qsi = self.source.get_qubit_index("Z", qz)
            if qsi == -1:
                px, py = ql
                if px - tx < py - ty:
                    circuitry.annotate_detector(f"TGT:EXP:R0:Z{qti}")
            else:
                circuitry.annotate_detector(f"TGT:EXP:R0:Z{qti}", f"SRC:REC:Z{qsi}")

        for ql, (qx, qti) in self.target.qubits["X"].items():
            qsi = self.source.get_qubit_index("X", qx)
            if qsi == -1:
                px, py = ql
                if px - tx > py - ty:
                    circuitry.annotate_detector(f"TGT:EXP:R0:X{qti}")
            else:
                circuitry.annotate_detector(f"TGT:EXP:R0:X{qti}", f"SRC:REC:X{qsi}")

        self.target.annotate_detectors(
            circuitry, rounds=self.target.distance, prefix="TGT:EXP"
        )
