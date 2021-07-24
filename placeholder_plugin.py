
# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pcbnew
import os
import re
import shutil
import subprocess

# Additional import for QRCode
# see https://github.com/kazuhikoarase/qrcode-generator/blob/master/python/qrcode.py
#import kicad_qrcode as qrcode  # TODO: local qrcode package is prefered, so we renamed it
import qrcode

# TODO Document!!
'''
How to generate a Sample QR-Code:
$ qrencode --structured --symversion 1 --size 1 --margin 1 --output qr.png "My Data"
$ # or the same in short:
$ qrencode -S -v 1 -s 1 -m 1 -o qr.png "My Data"
'''

# MIN_PIXEL_WIDTH = 0.5 * mm # TODO
MIN_PIXEL_WIDTH = 0.5 * 100000 # TODO Is this the correct multiplier
MIN_PIXEL_HEIGHT = MIN_PIXEL_WIDTH

import FootprintWizardBase

class QRCodeWizard(FootprintWizardBase.FootprintWizard):
    GetName = lambda self: '2D Barcode QRCode'
    GetDescription = lambda self: 'QR Code barcode generator'
    GetReferencePrefix = lambda self: 'QR***'
    GetValue = lambda self: self.module.Value().GetText()

    def GenerateParameterList(self):
        self.AddParam("Barcode", "Pixel Width", self.uMM, 0.5, min_value=0.4)
        self.AddParam("Barcode", "Border", self.uInteger, 0)
        self.AddParam("Barcode", "Contents", self.uString, 'Example')
        self.AddParam("Barcode", "Negative", self.uBool, False)
        self.AddParam("Barcode", "Use SilkS layer", self.uBool, True)
        self.AddParam("Barcode", "Use Cu layer", self.uBool, False)
        self.AddParam("Barcode", "Flip to back", self.uBool, False)
        self.AddParam("Caption", "Enabled", self.uBool, True)
        self.AddParam("Caption", "Height", self.uMM, 1.2)
        self.AddParam("Caption", "Width", self.uMM, 1.2)
        self.AddParam("Caption", "Thickness", self.uMM, 0.12)

    def CheckParameters(self):
        self.barcode = str(self.parameters['Barcode']['Contents'])
        self.pxWidth = self.parameters['Barcode']['Pixel Width']
        self.pxHeight = self.parameters['Barcode']['Pixel Height']
        self.negative = self.parameters['Barcode']['Negative']
        self.useSilkS = self.parameters['Barcode']['Use SilkS layer']
        self.useCu = self.parameters['Barcode']['Use Cu layer']
        self.onBack = self.parameters['Barcode']['Flip to back']
        self.border = int(self.parameters['Barcode']['Border'])
        self.textHeight = int(self.parameters['Caption']['Height'])
        self.textThickness = int(self.parameters['Caption']['Thickness'])
        self.textWidth = int(self.parameters['Caption']['Width'])
        self.pixelsSource = ImagePixelsSource("qr.png") # HACK
        self.module.Value().SetText(str(self.barcode))

if __name__ != "__main__":
    # Run as a KiCad plugin
    QRCodeWizard().register()
