<!--
SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>

SPDX-License-Identifier: CC0-1.0
-->

# KiCad QR-Code integrator

[![License: GPL-3.0-or-later](
https://img.shields.io/badge/License-GPL%203.0+-blue.svg)](
https://www.gnu.org/licenses/gpl-3.0.txt)
[![REUSE status](
https://api.reuse.software/badge/github.com/hoijui/kicad-image-injector)](
https://api.reuse.software/info/github.com/hoijui/kicad-image-injector)

status: WIP, pre-alpha

This tool might do one of two things in the end:

1. take a bunch of data (a string?),
   and create a QR-Code representing that data directly onto the PCB,
   creating one square object per each QR-Code pixel.
2. take an arbitrary B&W pixel-image (which might be a QR-Code),
   and reproduce it on the PCB in some way. (same as above?)

## The Files

* [qrcode.py](qrcode.py) -
  (foreign code)
  Given data (string), creates a QR-Code on a PCB, pixel by pixel.
  Use like this:

  ```
  # generate with explicit type number
  qr = QRCode()
  qr.setTypeNumber(4)
  qr.setErrorCorrectLevel(ErrorCorrectLevel.M)
  qr.addData('here comes qr!')
  qr.make()
  ```

* [qrcode_footprint_wizard.py](qrcode_footprint_wizard.py) -
  (foreign code)
  GUI/Plugin interface for `qrcode.py`
  
* [qrcode_tempalte_replacer.py](qrcode_tempalte_replacer.py) -
  WIP -
  Should be the KiCad GUI/plugin to place QR-Code/Image placeholders,
  later to be replaced automatically by TODO
  
* [placeholder2image.py](placeholder2image.py) -
  TODO -
  Given a KiCAD PCB file and a set of images,
  replaces all image-placeholders within the PCB with the actual images.
