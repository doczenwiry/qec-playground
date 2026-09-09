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

import stim


def annotate_noise(circuit: stim.Circuit):
    noisy = stim.Circuit()

    p = 0.01
    for instruction in circuit:
        noisy.append(instruction)

        if instruction.name == "CX":
            # targets_copy() is a flat list [control0, target0, control1, target1, ...]
            # DEPOLARIZE2 takes the same flat pairing, so we can pass it straight through.
            targets = [t.value for t in instruction.targets_copy()]
            noisy.append("DEPOLARIZE2", targets, p)

        elif instruction.name in ("RX", "R", "MX", "M"):
            targets = [t.value for t in instruction.targets_copy()]
            noisy.append("DEPOLARIZE1", targets, p)

    return noisy