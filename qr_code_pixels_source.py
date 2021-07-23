'''
Defines a class representing a black&white image of a QR-Code.
'''

# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pixels_source import PixelsSource

# see https://github.com/kazuhikoarase/qrcode-generator/blob/master/python/qrcode.py
#import kicad_qrcode as qrcode  # TODO: local qrcode package is prefered, so we renamed it
import qrcode

class QrCodePixelsSource(PixelsSource):
    '''
    Allows to use a string of data as sources for black&white pixels,
    encoded as a QR-Code.
    '''
    def __init__(self, content, border=1):
        self.border = border
        # Build QR-Code
        self.qrc = qrcode.QRCode()
        #self.qrc.setTypeNumber(4)
        # ErrorCorrectLevel: L = 7%, M = 15% Q = 25% H = 30%
        #self.qrc.setErrorCorrectLevel(qrcode.ErrorCorrectLevel.M)
        self.qrc.setErrorCorrectLevel(qrcode.ErrorCorrectLevel.L)
        self.qrc.addData(str(content))
        self.qrc.make()
        self.len = self.qrc.modules.__len__() + (self.border * 2)

    def getSize(self):
        return (self.len, self.len)

    def getData(self):
        if self.border >= 0:
            # Adding border: Create a new array larger than the self.qrc.modules
            array2d = [ [ 0 for a in range(self.len) ] for b in range(self.len) ]
            line_position = self.border
            for i in self.qrc.modules:
                column_position = self.border
                for j in i:
                    array2d[line_position][column_position] = j
                    column_position += 1
                line_position += 1
        else:
            # No border: using array as is
            array2d = self.qrc.modules
        data = []
        # convert 2D to 1D array
        for line in array2d:
            data.extend(line)
        return list(data)
