<!--
SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>

SPDX-License-Identifier: CC0-1.0
-->

# KiCad image/QR-Code integrator

[![License: GPL-3.0-or-later](
https://img.shields.io/badge/License-GPL%203.0+-blue.svg)](
https://www.gnu.org/licenses/gpl-3.0.txt)
[![REUSE status](
https://api.reuse.software/badge/github.com/hoijui/kicad-image-injector)](
https://api.reuse.software/info/github.com/hoijui/kicad-image-injector)

status: beta

## What is this

A stand-alone (python) tool
to replace rectangular template areas drawn onto a KiCad PCB
with B&W images or QR-Codes.

This was written with the intention to include QR-Codes
containing git-commit specific information
onto a PCB and later the generated Gerber & Drill files
in a CI job.

## What it does

pseudo code (python):

```python
pcb = parseKicadPcb("some_board.kicad_pcb")
placeholders = scanForPlaceholderRectangles(pcb)
replacements = cli_args.getAsList("replacements")
if len(placeholders) != len(replacements):
    print("Bad!")
    exit(1)
for i in range(0, len(placeholders)):
    p_holder = placeholders[i]
    repl = replacements[i]
    if isSkip(repl):
        continue
    elif isImage(repl):
       pixels = loadImagePixels(p_holder.imagePath)
    elif isQrData(repl):
       pixels = generateQrCode(p_holder.data)
    pcb.replace(p_holder, pixels)
pcb.writeKicadPcb("some_board-REPLACED.kicad_pcb")
```

## Usage

1. Design your PCB in KiCad
    and include rectangular polygons on any silk or copper layer.
    See [below](#creating-placeholders) for more detailed instructions.

2. Make sure the images you want to inject are available (e.g. generate them).

3. Run this tool with the appropriate number of arguments
    (image paths, qr-code data strings or skip instructions).
    In the case of three placeholder rectangles, it could be:

    ```bash
    python3 placeholder2image.py ~/some/path/board.kicad_pcb qr.png skip 'qr:My Data'
    ```

    NOTE: Take care of using the [correct order](#order-of-placeholders)
    of the supplied replacements.

4. Done!
   Do what you want with the generated PCB:
   `~/some/path/board-REPLACED.kicad_pcb`

Run `python3 placeholder2image.py --help` for more info.

### Placeholders

As the KiCad PCB file format does not allow for much meta-data to be added to elements,
we treat all axis-aligned, rectangular polygons as viable placeholders.
If you do not want to replace some of those,
you have to explicitly tell this tool to *skip* them.

#### Creating Placeholders

1. Open your PCB in KiCad (`pcbnew`),
2. select the menu item `Place -> Polygon`,
3. draw an axis-aligned rectangle
   (don't worry if it is not perfect, you can adjust it after creation),
4. right-click on it,
5. select `Properties...`,
6. select the layer you want
   (any of: `F.Cu`, `B.Cu`, `F.SilkS`, `B.SilkS`).

**NOTE** \
If a polygon does not have exactly 4 points,
and is not perfectly axis aligned,
it will not be recognized!

Take note of how many rectangles you created!

#### Order of Placeholders

The order of the repalcement pixels sources supplied on the command-line is important,
and has to correspond exactly to the order of the placeholders in the PCB.

The order of the placeholders on the PCB is defined as follows
(higher up in this list is more important):

1. copper before silk
2. front before back
3. top-left corner up before down
4. top-left corner left before right
5. bottom-right corner up before down
6. bottom-right corner left before right
7. polygon before zone

## Example Usage

input:

![input QR-Code](qr.png)
(generated with: `qrencode -s 1 -m 1 -o qr.png "My Data"`)

[![input PCB](kicad-board-0-design.svg)](https://github.com/hoijui/for-science-keyboar/base.kicad_pcb)

output:

![output PCB](kicad-board-1-generated.svg)
