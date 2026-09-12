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
from enum import Enum
from typing import Optional, Final, Callable

import stim
import logging

from library.qubit_array import QubitArray

logger = logging.getLogger(__name__)

class PauliBasis(Enum):
    X = 0
    Y = 1
    Z = 2

class SurfaceCodePatch:
    MOMENTS: Final[range] = range(6)
    SCHEDULE_X = [ (-0.5, -0.5) , (+0.5, -0.5) , (-0.5, +0.5) , (+0.5, +0.5) ]
    SCHEDULE_Z = [ (-0.5, -0.5) , (-0.5, +0.5) , (+0.5, -0.5) , (+0.5, +0.5) ]

    def __init__(self, qubits: QubitArray, distance: int = 3, anchor: tuple[int,int] = (1, 1)):
        self.__anchor = anchor
        self.__distance = distance
        self.__physical_qubits = qubits
        ax, ay = anchor
        self.data_qubits: dict[tuple[float, float], tuple[int,int]] = {
            location : (qubits[location], index)
            for index, location in enumerate(itertools.product(
                range(ax, ax + distance),
                range(ay, ay + distance)
            ))
        }
        ancilla_count = (distance**2 - 1) // 2
        width = 1 + (distance // 2)
        self.z_ancilla: dict[tuple[float,float], tuple[int,int]] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) - ((q // width) % 2), ay + 0.5 + (q // width))
            self.z_ancilla[location] = (qubits[location], len(self.z_ancilla))
        width = distance // 2
        self.x_ancilla: dict[tuple[float,float], tuple[int,int]] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) + ((q // width) % 2), ay - 0.5 + (q // width))
            self.x_ancilla[location] = (qubits[location], len(self.x_ancilla))

    @property
    def distance(self):
        return self.__distance

    @property
    def anchor(self):
        return self.__anchor

    @property
    def num_qubits(self):
        return len(self.data_qubits) + len(self.z_ancilla) + len(self.x_ancilla)

    def __data_qubits(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (dl, dqi) for dl, dqi in self.data_qubits.items() if not inactive(dl)
        )

    def __z_ancilla(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (zl, zqi) for zl, zqi in self.z_ancilla.items() if not inactive(zl)
        )

    def __x_ancilla(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (xl, xqi) for xl, xqi in self.x_ancilla.items() if not inactive(xl)
        )

    def get_qubit_at_location(self, location: tuple[float, float]) -> int:
        return self.data_qubits[location][0] if location in self.data_qubits  else -1

    def __get_polygon(self, px, py):
        return [
            self.get_qubit_at_location( (px+dx, py+dy) ) for dx, dy in
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location( (px+dx, py+dy) ) != -1
        ]

    def get_polygons(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        polygons = []
        for location, _ in self.__z_ancilla(inactive):
            polygon = self.__get_polygon(*location)
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        for location, _ in self.__x_ancilla(inactive):
            polygon = self.__get_polygon(*location)
            polygons.append(f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_memory(
            self, circuit: stim.Circuit, memory: int,
            prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
            full_ft: bool = True, prefix: str = ""
    ):
        start = 0
        final = self.__distance - 1
        for rnd in range(self.__distance if full_ft else 1):
            self.append_round(
                circuit,
                prepare = prepare if (rnd == start) else None,
                measure = measure if (rnd == final) else None,
                prefix = f"{prefix}:M{memory}:R{rnd}"
            )

    def append_round(
        self, circuit: stim.Circuit, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
        inactive: Callable[[tuple[float,float]], bool] = lambda _: False, prefix: str = ""
    ):
        for mmt in SurfaceCodePatch.MOMENTS:
            self.append_round_slice(circuit, mmt, prepare, measure, inactive, prefix)
            circuit.append("TICK")

    def append_round_slice(
        self, circuit: stim.Circuit, moment: int, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
        inactive: Callable[[tuple[float,float]], bool] = lambda _: False, prefix: str = ""
    ):
        match moment:
            case 0:
                circuit.append("RZ", [za for _, (za,_) in self.__z_ancilla(inactive)])
                circuit.append("RX", [xa for _, (xa,_) in self.__x_ancilla(inactive)])
                if prepare:
                    circuit.append(f"R{prepare.name}", [qd for _, (qd,_) in self.__data_qubits(inactive)])
            case 1 | 2 | 3 | 4:
                targets = []
                for (px,py), (qz, _) in self.__z_ancilla(inactive):
                        dx, dy = SurfaceCodePatch.SCHEDULE_Z[moment - 1]
                        qd = self.get_qubit_at_location( (px+dx, py+dy) )
                        if qd != -1:
                            targets.append(qd)
                            targets.append(qz)
                for (px,py), (qx, _) in self.__x_ancilla(inactive):
                        dx, dy = SurfaceCodePatch.SCHEDULE_X[moment - 1]
                        qd = self.get_qubit_at_location( (px+dx, py+dy) )
                        if qd != -1:
                            targets.append(qx)
                            targets.append(qd)
                circuit.append("CX", targets)
            case 5:
                measured_z_ancilla = []
                for zl, (zq, zi) in self.__z_ancilla(inactive):
                    self.__physical_qubits.record_measurement(zq, f"{prefix}:Z{zi}")
                    measured_z_ancilla.append(zq)
                circuit.append("MZ", measured_z_ancilla)
                measured_x_ancilla = []
                for xl, (xq, xi) in self.__x_ancilla(inactive):
                    self.__physical_qubits.record_measurement(xq, f"{prefix}:X{xi}")
                    measured_x_ancilla.append(xq)
                circuit.append("MX", measured_x_ancilla)
                if measure:
                    measured_data = []
                    for dl, (dq, di) in self.__data_qubits(inactive):
                        self.__physical_qubits.record_measurement(dq, f"{prefix}:D{di}")
                        measured_data.append(dq)
                    circuit.append(f"M{measure.name}", measured_data)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")