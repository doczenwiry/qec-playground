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
from typing import Optional, Callable

import stim

import logging

from library.qubit_allocation import QubitAllocation

logger = logging.getLogger(__name__)

class SurfaceCodePatch:
    SCHEDULE_X = [ (-0.5, -0.5) , (+0.5, -0.5) , (-0.5, +0.5) , (+0.5, +0.5) ]
    SCHEDULE_Z = [ (-0.5, -0.5) , (-0.5, +0.5) , (+0.5, -0.5) , (+0.5, +0.5) ]

    def __init__(self, distance: int, allocation: QubitAllocation, anchor: tuple[int, int] = (1, 1)):
        self.__anchor = anchor
        self.__distance = distance
        self.__allocation = allocation
        ax, ay = anchor
        self.qubits = {
            location : allocation[location]
            for location in itertools.product(
                range(ax, ax + distance),
                range(ay, ay + distance)
            )
        }
        ancilla_count = (distance**2 - 1) // 2
        width = 1 + (distance // 2)
        qubit_offset = len(self.qubits)
        self.z_ancilla = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) - ((q // width) % 2), ay + 0.5 + (q // width))
            self.z_ancilla[location] = allocation[location]
        width = distance // 2
        qubit_offset += len(self.z_ancilla)
        self.x_ancilla = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) + ((q // width) % 2), ay - 0.5 + (q // width))
            self.x_ancilla[location] = allocation[location]

    @property
    def moments(self):
        return range(6)

    @property
    def num_qubits(self):
        return len(self.qubits) + len(self.z_ancilla) + len(self.x_ancilla)

    def __z_ancilla(self, exclude):
        return filter(lambda za : not exclude(za), self.z_ancilla.items())

    def __x_ancilla(self, exclude):
        return filter(lambda xa : not exclude(xa), self.x_ancilla.items())

    def get_qubit_at_location(self, location: tuple[float, float]) -> int:
        return self.__allocation[location] if location in self.qubits else -1

    def __get_polygon(self, px, py):
        return [
            self.get_qubit_at_location( (px+dx, py+dy) ) for dx, dy in
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location( (px+dx, py+dy) ) != -1
        ]

    def get_polygons(self, exclude):
        polygons = []
        for (px,py), qubit in self.__z_ancilla(exclude):
            polygon = self.__get_polygon(px, py)
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        for (px,py), qubit in self.__x_ancilla(exclude):
            polygon = self.__get_polygon(px, py)
            polygons.append(f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_metadata(self, circuit: stim.Circuit):
        for qubit, location in self.qubits.items():
            circuit.append("QUBIT_COORDS", [qubit], location)
        for qubit, location in self.z_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)
        for qubit, location in self.x_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)

    def append_syndrome(self, circuit: stim.Circuit, preparation: bool = False, *exclude: tuple[float, float]):
        for moment in self.moments:
            self.append_syndrome_slice(circuit, moment, preparation, *exclude)

    def append_syndrome_slice(self, circuit: stim.Circuit, moment: int, preparation: bool = False, *exclude: tuple[float, float]):
        match moment:
            case 0:
                circuit.append("RX", self.z_ancilla.values())
                circuit.append("RX", self.x_ancilla.values())
                if preparation:
                    circuit.append("RX", self.qubits.values())
            case 1 | 2 | 3 | 4:
                for gate, ancilla, schedule in [
                    ("CZ", self.z_ancilla, SurfaceCodePatch.SCHEDULE_Z),
                    ("CX", self.x_ancilla, SurfaceCodePatch.SCHEDULE_X)
                ]:
                    gates = []
                    for (px,py), qa in ancilla.items():
                        dx, dy = schedule[moment - 1]
                        target = self.get_qubit_at_location( (px+dx, py+dy) )
                        if target != -1:
                            gates.append(qa)
                            gates.append(target)
                    circuit.append(gate, gates)
            case 5:
                circuit.append("MX", self.z_ancilla.values())
                circuit.append("MX", self.x_ancilla.values())
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")