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

status: WIP,  tech-demo, alpha

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
for p_holder in placeholders:
    if referencesImage(p_holder):
       pixels = loadImagePixels(p_holder.imagePath)
    elif referencesQrData(p_holder):
       pixels = generateQrCode(p_holder.data)
    pcb.replace(p_holder, pixels)
pcb.writeKicadPcb("some_board-REPLACED.kicad_pcb")
```

## Usage

1. You design your PCB in KiCad,
    and include rectangular areas on any silk or copper layer.
    In the description of the rectangular drawing (silk layer) or zone (copper layer),
    you either reference the image path,
    or the data to be included as a QR-code.

    **TODO** \
    Actually make this work and maybe implement a GUI plugin to guide though this,
    ensuring correct encoding of this meta-data in the description.

2. Make sure (e.g. generate) the referenced images are available.

3. run this tool, e.g.:

    ```bash
    python3 placeholder2image.py ~/some/path/board.kicad_pcb
    ```

4. do what you want with the generated PCB:
   `~/some/path/board-REPLACED.kicad_pcb`

Run `python3 placeholder2image.py --help` for more info.

## Example

input:

![input QR-Code](qr.png)
(generated with: `qrencode -s 1 -m 1 -o qr.png "My Data"`)

[![input PCB](kicad-board-0-design.svg)](https://github.com/hoijui/for-science-keyboar/base.kicad_pcb)

output:

![output PCB](kicad-board-1-generated.svg)
