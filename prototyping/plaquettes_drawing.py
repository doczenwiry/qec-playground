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
import numpy as np
from PIL import Image, ImageDraw, ImageFont

UNIT = 64

SCHEDULE_ORDER = [ 0, 1, 3, 2 ]
SQUARE = [ (0,0), (1,0), (1,1), (0,1) ]
RECTANGLE = [ (0,0), (1,0), (1,2), (0,2) ]
TRIANGLE_TL = [ (0.6, 0), (1,0), (1, 2), (0, 2), (0, 1.6) ]
TRIANGLE_BR = [ (0,0), (1,0), (1, 0.4), (0.4, 2), (0, 2) ]
SQUARE_TRIM0 = [ (1,0), (1,1), (0,1) ]
SQUARE_TRIM1 = [ (0,0), (1,1), (0,1) ]
SQUARE_TRIM2 = [ (0,0), (1,0), (1,1) ]
SQUARE_TRIM3 = [ (0,0), (1,0), (0,1) ]

CHORD_T = ( [ 0.0, 0.5, 1.0, 1.5] , 180, 360 )
CHORD_R = ( [-0.5, 0.0, 0.5, 1.0] , 270,  90 )
CHORD_B = ( [ 0.0,-0.5, 1.0, 0.5] ,   0, 180 )
CHORD_L = ( [ 0.5, 0.0, 1.5, 1.0] ,  90, 270 )

PLAQUETTE_SHAPES = {
    0: SQUARE, 1: SQUARE, 2: SQUARE, 3: SQUARE, 4: SQUARE, 5: SQUARE, 6: SQUARE, 7: SQUARE,
    12: RECTANGLE, 13: RECTANGLE, 14: TRIANGLE_TL, 15: TRIANGLE_BR,
    16: SQUARE_TRIM0, 17: SQUARE_TRIM1, 18: SQUARE_TRIM2, 19: SQUARE_TRIM3,
}
PLAQUETTE_CHORDS = {
    8 : CHORD_T, 9 : CHORD_R, 10 : CHORD_B, 11 : CHORD_L
}

def make_shape(position, base_shape, scale):
    x, y = position
    return [((x+dx) * scale , (y+dy) * scale) for dx, dy in base_shape]

def make_chord(position, base_shape, scale):
    x, y = position
    x0, y0, x1, y1 = base_shape
    return [ (x0+x) * scale , (y0+y) * scale, (x1+x) * scale , (y1+y) * scale ]

def draw_plaquettes(
    junction: np.ndarray, regular_schedules, extended_schedules,
    direction = 'forward', savefile = None
):
    height, width = junction.shape
    image = Image.new("RGB", (width * UNIT, height * UNIT), "gray")

    drawer = ImageDraw.Draw(image)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size=16)

    for row, col in itertools.product(range(width), range(height)):
        ptype = junction[row,col]

        if ptype == 255:
            continue

        color = "#CF4040" if 0 <= ptype <= 3 or ptype == 12 else "#4040CF"

        if 8 <= ptype <= 11:
            parameters, start, final = PLAQUETTE_CHORDS[ptype]
            drawer.chord(
                make_chord((col,row), parameters, UNIT), start=start, end=final,
                fill=color, outline="black", width=3
            )
        else:
            drawer.polygon(
                make_shape( (col, row), PLAQUETTE_SHAPES[ptype], UNIT),
                fill=color, outline="black", width=3
            )

    for row, col in itertools.product(range(width), range(height)):
        ptype = junction[row, col]

        if ptype == 255:
            continue

        count = 0
        touched = set()
        for index, (pr, pc) in enumerate([ (-1,-1), (-1, 0), ( 0,-1), (0, 0) ]):
            if not (0 <= row+pr < height and 0 <= col+pc < width):
                continue
            ntype = junction[row+pr, col+pc]
            if 0 <= ntype <= 11 or 16 <= ntype <= 19:
                moment = regular_schedules['forward'][ntype][3 - index]
                touched.add(moment)
                count += 1

        if len(touched) != count:
            bounding = [ pos * UNIT for pos in [ col-0.375, row-0.375, col+0.375, row+0.375 ] ]
            drawer.ellipse(bounding, fill="#FFFF0020", outline="black", width=3)

    for row, col in itertools.product(range(width), range(height)):
        ptype = junction[row, col]

        if ptype == 255:
            continue

        color = "#CF4040" if 0 <= ptype <= 3 or ptype == 12 else "#4040CF"

        # Go over the schedule and place the number at the corresponding corner.
        if 0 <= ptype <= 7 or 12 <= ptype <= 13 or 16 <= ptype <= 19:
            shape = SQUARE if 0 <= ptype <= 7 or 16 <= ptype <= 19 else RECTANGLE # PLAQUETTE_SHAPES[ptype]
            if 0 <= ptype <= 7:
                schedules = regular_schedules
                last_qubits_moments = sorted(schedules[direction][ptype], reverse=True)[:2]
            elif 12 <= ptype <= 13:
                schedules = extended_schedules
                last_qubits_moments = [3, 5]
            elif 16 <= ptype <= 19:
                schedules = regular_schedules
                last_qubits_moments = []
            cx = sum(x for x,_ in shape) / len(shape)
            cy = sum(y for _,y in shape) / len(shape)
            x, y = col + cx, row + cy
            last_qubits = []
            for index, (dx, dy) in enumerate(shape):
                moment = schedules[direction][ptype][SCHEDULE_ORDER[index]]
                if moment == 0:
                    continue

                px, py = x + 0.65 * (dx - cx), y + 0.65 * (dy - cy)
                if moment in last_qubits_moments:
                    last_qubits.append( (px * UNIT, py * UNIT) )
                drawer.text( (px * UNIT, py * UNIT), text=str(moment), fill="black", anchor="mm", font=font)
            if len(last_qubits) == 2:
                h1, h2 = last_qubits
                trim = 0.20
                sh1 = tuple(np.array(h1) + trim * (np.array(h2) - np.array(h1)))
                sh2 = tuple(np.array(h2) - trim * (np.array(h2) - np.array(h1)))
                drawer.line( [ sh1, sh2 ], fill="black", width=10)
                drawer.line([sh1, sh2], fill=color, width=5)
        elif 14 <= ptype <= 15:
            shape = [ (0,0), (1,0), (1,2), (0,2) ]
            last_qubits_moments = [3, 5]
            schedules = extended_schedules
            cx = sum(x for x,_ in shape) / len(shape)
            cy = sum(y for _,y in shape) / len(shape)
            x, y = col + cx, row + cy
            last_qubits = []
            for index, (dx, dy) in enumerate(shape):
                moment = schedules[direction][ptype][SCHEDULE_ORDER[index]]
                if moment == 0:
                    continue

                px, py = x + 0.65 * (dx - cx), y + 0.65 * (dy - cy)
                if moment in last_qubits_moments:
                    last_qubits.append( (px * UNIT, py * UNIT) )
                drawer.text( (px * UNIT, py * UNIT), text=str(moment), fill="black", anchor="mm", font=font)
            if len(last_qubits) == 2:
                h1, h2 = last_qubits
                trim = 0.20
                sh1 = tuple(np.array(h1) + trim * (np.array(h2) - np.array(h1)))
                sh2 = tuple(np.array(h2) - trim * (np.array(h2) - np.array(h1)))
                drawer.line( [ sh1, sh2 ], fill="black", width=10)
                drawer.line([sh1, sh2], fill=color, width=5)
        elif 8 <= ptype <= 11:
            shape = [(0, 0), (1, 0), (1, 1), (0, 1)]
            schedules = regular_schedules
            cx = sum(x for x, _ in shape) / len(shape)
            cy = sum(y for _, y in shape) / len(shape)
            x, y = col + cx, row + cy
            for index, (dx, dy) in enumerate(shape):
                moment = schedules[direction][ptype][SCHEDULE_ORDER[index]]
                if moment == 0:
                    continue

                px, py = x + 0.65 * (dx - cx), y + 0.65 * (dy - cy)
                drawer.text((px * UNIT, py * UNIT), text=str(moment), fill="black", anchor="mm", font=font)

    if savefile:
        image.save(savefile)
    else:
        image.show()
