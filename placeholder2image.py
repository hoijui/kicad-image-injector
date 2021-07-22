
# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

#  last change: 2017, Jan 4.

import pcbnew
import os
import re
import shutil
import subprocess
import click

from PIL import Image

# Additional import for QRCode
# see https://github.com/kazuhikoarase/qrcode-generator/blob/master/python/qrcode.py
#import kicad_qrcode as qrcode  # TODO: local qrcode package is prefered, so we renamed it
import qrcode

# TODO Document!!
'''
How to generate a Sample QR-Code:
$ qrencode --structured --symversion 1 --size 1 --margin 1 --output qrx.png "My Data"
$ # or the same in short:
$ qrencode -S -v 1 -s 1 -m 1 -o qrx.png "My Data"
'''

# MIN_PIXEL_WIDTH = 0.5 * mm # TODO
MIN_PIXEL_WIDTH = 0.5 * 100000 # TODO Is this the correct multiplier
MIN_PIXEL_HEIGHT = MIN_PIXEL_WIDTH

class PixelsSource:
    def getData(self):
        '''
        Returns an array containing the pixels to draw.
        It starts with the first pixel on the left of the top-most line,
        continues with the second pixel on the same line,
        until the end of the line, and then continues with the first pixel
        on the left of the second line from the top.
        each pixel may only have two values:
        * "off" -> 0
        * "on"  -> 1 or 255
        '''
        return []

    def getSize(self):
        return (0, 0)

    def debugAsAsciiToStdout(self) -> None:
        width = self.getSize()[0]
        #height = self.getSize()[1]
        lpi = 0
        li = 0
        for pixel in self.getData():
            if pixel == 0:
                pc = ' '
            else:
                pc = '1'
            print(pc, end = '')
            lpi = lpi + 1
            lpi = lpi % width
            if lpi == 0:
                li = li + 1
                print()

def load_as_binary_image(image_path):
    try:
        with Image.open(image_path) as img:
            # print(image_path, img.format, f"{img.size}x{img.mode}")
            if img.mode != "1":
                img = img.convert("L")
                img = img.convert("1")
            return img
    except OSError:
        pass

class ImagePixelsSource(PixelsSource):
    def __init__(self, image_path):
        self.image = load_as_binary_image(image_path)

    def getSize(self):
        return self.image.size

    def getData(self):
        return self.image.getdata()

class QrCodePixelsSource(PixelsSource):
    def __init__(self, content, border=1):
        self.border = border
        # Build QR-Code
        self.qr = qrcode.QRCode()
        #self.qr.setTypeNumber(4)
        # ErrorCorrectLevel: L = 7%, M = 15% Q = 25% H = 30%
        #self.qr.setErrorCorrectLevel(qrcode.ErrorCorrectLevel.M)
        self.qr.setErrorCorrectLevel(qrcode.ErrorCorrectLevel.L)
        self.qr.addData(str(content))
        self.qr.make()
        self.len = self.qr.modules.__len__() + (self.border * 2)

    def getSize(self):
        return (self.len, self.len)

    def getData(self):
        if self.border >= 0:
            # Adding border: Create a new array larger than the self.qr.modules
            arrayToDraw = [ [ 0 for a in range(self.len) ] for b in range(self.len) ]
            linePosition = self.border
            for i in self.qr.modules:
                columnPosition = self.border
                for j in i:
                    arrayToDraw[linePosition][columnPosition] = j
                    columnPosition += 1
                linePosition += 1
        else:
            # No border: using array as is
            arrayToDraw = self.qr.modules
        data = []
        # convert 2D to 1D array
        for line in arrayToDraw:
            data.extend(line)
        return list(data)

def _minus(vec1, vec2) -> (int, int):
    return (vec1[0] - vec2[0], vec1[1] - vec2[1])

def _plus(vec1, vec2) -> (int, int):
    return (vec1[0] + vec2[0], vec1[1] + vec2[1])

def _mult(vec1, vec2) -> (int, int):
    return (vec1[0] * vec2[0], vec1[1] * vec2[1])

def _div(vec1, vec2) -> (int, int):
    return (int(vec1[0] / vec2[0]), int(vec1[1] / vec2[1]))

def _modulo(vec1, vec2) -> (int, int):
    return (vec1[0] % vec2[0], vec1[1] % vec2[1])

class Replacement:
    def __init__(self, pcb, placeholderDrawing, topLeft: int, bottomRight: int, pixelsSource: PixelsSource, stretch: bool = False, negative: bool = False):
        self.pcb = pcb
        self.placeholderDrawing = placeholderDrawing
        self.topLeft = topLeft
        self.bottomRight = bottomRight
        self.pixelsSource = pixelsSource
        self.stretch = stretch
        self.negative = negative
        self.sizeSpace = _minus(self.bottomRight, self.topLeft)
        self.sizeRepl = self.pixelsSource.getSize()
        self.sizePixel = self._calcPixelSize()
        self.reverse = pcbnew.B_SilkS in self.placeholderDrawing.GetLayerSet().Seq() or pcbnew.B_Cu in self.placeholderDrawing.GetLayerSet().Seq()
        self.firstPixelPos = self._calcFirstPixelPos()

    def _calcPixelSize(self) -> (int, int):
        maxPixelSize = _div(self.sizeSpace, self.sizeRepl)
        if self.stretch:
            pixelSize = maxPixelSize
        else:
            minBoth = min(maxPixelSize)
            pixelSize = (minBoth, minBoth)
        if pixelSize[0] < MIN_PIXEL_WIDTH:
            raise RuntimeError("Replacement image is too large (width) for the template area")
        if pixelSize[1] < MIN_PIXEL_HEIGHT:
            raise RuntimeError("Replacement image is too large (height) for the template area")
        return pixelSize
    
    def _calcFirstPixelPos(self) -> (int, int):
        border = _minus(self.sizeSpace, _mult(self.sizeRepl, self.sizePixel))
        border = _div(border, (2, 2))
        if self.reverse:
            firstPixelPos = (self.bottomRight[0] - border[0], self.topLeft[1] + border[1])
        else:
            firstPixelPos = self.topLeft + border
        return firstPixelPos

    def _createAxisAlignedSilkRect(self, module: pcbnew.MODULE, pos: (int, int), size: (int, int)):
        # build a polygon (a square) on silkscreen
        # creates a EDGE_MODULE of polygon type. The polygon is a square
        # print("_createAxisAlignedSilkRect(%s, %s, %s)" % (module, pos, size))
        polygon = pcbnew.EDGE_MODULE(module)
        polygon.SetShape(pcbnew.S_POLYGON)
        polygon.SetWidth( 0 )
        layer = self.placeholderDrawing.GetLayerSet().Seq()[0]
        polygon.SetLayer(layer)
        polygon.GetPolyShape().NewOutline()
        polygon.GetPolyShape().Append(  pos[0] + size[0], pos[1] + size[1] )
        polygon.GetPolyShape().Append(  pos[0] + size[0], pos[1] )
        polygon.GetPolyShape().Append(  pos[0], pos[1] )
        polygon.GetPolyShape().Append(  pos[0], pos[1] + size[1] )
        return polygon

    def _createSilkPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        return self._createAxisAlignedSilkRect(module, pos, self.sizePixel)

    def _createCuPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        # build a rectangular pad as a dot on copper layer,
        print("_createCuPixel(%s, %s, %s)" % (module, pos, index))
        pad = pcbnew.D_PAD(module)
        pad.SetSize(pcbnew.wxSize(self.sizePixel[0], self.sizePixel[1]))
        pad.SetPosition(pcbnew.wxPoint(pos[0], pos[1]))
        pad.SetLocalCoord()
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetName("")
        layerset = pcbnew.LSET()
        if pcbnew.F_Cu in self.placeholderDrawing.GetLayerSet().Seq():
            layerset.AddLayer(pcbnew.F_Cu)
            layerset.AddLayer(pcbnew.F_Mask)
        else:
            layerset.AddLayer(pcbnew.B_Cu)
            layerset.AddLayer(pcbnew.B_Mask)
        # layerset = self.placeholderDrawing.GetLayerSet()
        pad.SetLayerSet(layerset)
        return pad

    def _drawPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        # build a rectangular pad as a dot on copper layer,
        # and a polygon (a square) on silkscreen
        if pcbnew.F_SilkS in self.placeholderDrawing.GetLayerSet().Seq() or pcbnew.B_SilkS in self.placeholderDrawing.GetLayerSet().Seq():
            pixel = self._createSilkPixel(module, index, pos)
        else:
            pixel = self._createCuPixel(module, index, pos)
        module.Add(pixel)

    def _drawPixels(self):
        module = pcbnew.MODULE(self.pcb)
        # module.SetPosition(0, 0)
        module.SetDescription("Replaced template - ... - TODO") # TODO Use this for meta-data, eg. replacement image path
        module.SetLayer(pcbnew.F_SilkS) # HACK Needs to be set dynamically/fro a variable

        pos = self.firstPixelPos
        pi = 0
        xi = 0
        yi = 0
        for px in self.pixelsSource.getData():
            if (px != 0 and not self.negative) or (px == 0 and self.negative):
                self._drawPixel(module, pi, pos)
            pi = pi + 1
            xi = (xi + 1) % self.sizeRepl[0]
            if xi == 0:
                yi = yi + 1
                posAdjust = (-(self.sizePixel[0] * (self.sizeRepl[0] - 1)), self.sizePixel[1])
            else:
                posAdjust = (self.sizePixel[0], 0)
            if self.reverse:
                posAdjust = _mult((-1, 1), posAdjust)
            pos = _plus(pos, posAdjust)
        #module.Add(self._createAxisAlignedSilkRect(module, (0, 0), (168402000, 168402000))) # HACK Just draw a huge rect, to see if it is visible -> Yes it is! :-)
        self.pcb.Add(module)

    def _drawCaption(self):

        # used many times...
        # half_number_of_elements = arrayToDraw.__len__() / 2
        width = self.pixelsSource.getSize()[0]
        halfWidth = width / 2

        #int((5 + half_number_of_elements) * self.pxWidth))
        textPosition = int((self.textHeight) + ((1 + halfWidth) * self.pxWidth))
        module = self.placeholderDrawing.GetParent()

        module.Value().SetTextHeight(self.textHeight)
        module.Value().SetTextWidth(self.textWidth)
        module.Value().SetThickness(self.textThickness)
        module.Reference().SetTextHeight(self.textHeight)
        module.Reference().SetTextWidth(self.textWidth)
        module.Reference().SetThickness(self.textThickness)
        if self.reverse:
            module.Value().Flip(pcbnew.wxPoint(0, 0))
            module.Reference().Flip(pcbnew.wxPoint(0, 0))
            textLayer = pcbnew.B_SilkS
        else:
            textLayer = pcbnew.F_SilkS
        module.Value().SetPosition(pcbnew.wxPoint(0, - textPosition))
        module.Reference().SetPosition(pcbnew.wxPoint(0, textPosition))
        module.Value().SetLayer(textLayer)

def extractCorners(obj, polySet):
    xs = set()
    ys = set()
    for pi in range(0, 4):
        point = polySet.CVertex(pi)
        print("  point: (%d, %d)" % (point.x, point.y))
        xs.add(point.x)
        ys.add(point.y)
    print(len(xs))
    print(len(ys))
    # Check if it is an axis-aligned rectangle
    if len(xs) != 2 or len(ys) != 2:
        raise RuntimeWarning("Not an axis-ligned rectangle: %s" % obj)
    topLeft = (min(xs), min(ys))
    bottomRight = (max(xs), max(ys))
    print("top-left: %d, %d" % topLeft)
    print("bottom-right: %d, %d" % bottomRight)
    return (topLeft, bottomRight)

def replace_all(pcb, images_root):
    replacements = []

    for zone in pcb.Zones():
        print(zone)
        ps = zone.Outline()
        if ps.OutlineCount() == 1 and ps.VertexCount() == 4:
            # ps = zone.GetPolyShape()
            try:
                (topLeft, bottomRight) = extractCorners(zone, ps)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            pixelsSource = ImagePixelsSource("qrx.png") # HACK
            replacement = Replacement(pcb, zone, topLeft, bottomRight, pixelsSource)
            replacements.append(replacement)

    for drawing in pcb.GetDrawings():
        if drawing.GetClass() == "DRAWSEGMENT" and drawing.GetShape() == pcbnew.S_POLYGON and drawing.GetPointCount() == 4 and drawing.GetPolyShape().OutlineCount() == 1 and drawing.GetPolyShape().HoleCount(0) == 0:
            print(drawing)
            ps = drawing.GetPolyShape()
            try:
                (topLeft, bottomRight) = extractCorners(drawing, ps)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            pixelsSource = ImagePixelsSource("qrx.png") # HACK
            replacement = Replacement(pcb, drawing, topLeft, bottomRight, pixelsSource)
            replacements.append(replacement)

    for repl in replacements:
        repl._drawPixels()

    for repl in replacements:
        pcb.Remove(repl.placeholderDrawing)

# The CLI interface
@click.command()
@click.argument('kicad_pcb_in_file')
@click.argument('kicad_pcb_out_file', required=0)
@click.argument('images_root', required=0)
def replace_all_cli(kicad_pcb_in_file, kicad_pcb_out_file=None, images_root=None):
    """Replaces all QR-Code template polygons with the actual QR-Code image,
    both on the Copepr and Silkscreen layers,
    on the front and on the back, in a KiCad PCB file (*.kicad_pcb).

    KICAD_PCB_IN_FILE - The path to the `*.kicad_pcb` input file to replace QR-Code templates in
    KICAD_PCB_OUT_FILE - The path to the `*.kicad_pcb` output file
    """
    R_KICAD_PCB_EXT = re.compile("\.kicad_pcb$")
    if kicad_pcb_out_file is None:
        kicad_pcb_out_file = R_KICAD_PCB_EXT.sub("-REPLACED.kicad_pcb", kicad_pcb_in_file)
    if images_root is None:
        images_root = os.curdir
    
    if kicad_pcb_in_file == kicad_pcb_out_file:
        raise RuntimeError("KiCad PCB input and output file names can not be the same!")

    pcb = pcbnew.LoadBoard(kicad_pcb_in_file)
    replace_all(pcb, images_root)
    pcbnew.SaveBoard(kicad_pcb_out_file, pcb)
    print(kicad_pcb_in_file)
    print(kicad_pcb_out_file)

def testing():
    image_path = "qrx.png"
    ps = ImagePixelsSource(image_path)
    ps.debugAsAsciiToStdout()

    print()

    ps = QrCodePixelsSource("My Data", 1)
    ps.debugAsAsciiToStdout()

if __name__ == "__main__":
    # Run as a CLI script
    testing()
    replace_all_cli()
    exit(1)




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
        self.pixelsSource = ImagePixelsSource("qrx.png") # HACK
        self.module.Value().SetText(str(self.barcode))

    # def drawSquareArea(self, layer, size, xPosition, yPosition):
    #     # creates a EDGE_MODULE of polygon type. The polygon is a square
    #     polygon = pcbnew.EDGE_MODULE(self.module)
    #     polygon.SetShape(pcbnew.S_POLYGON)
    #     polygon.SetWidth( 0 )
    #     polygon.SetLayer(layer)
    #     halfsize = size/2
    #     polygon.GetPolyShape().NewOutline()
    #     pos = pcbnew.wxPoint(xPosition, yPosition)
    #     polygon.GetPolyPoints().Append( pcbnew.wxPoint( halfsize, halfsize  ) + pos )
    #     polygon.GetPolyPoints().Append( pcbnew.wxPoint( halfsize, -halfsize ) + pos )
    #     polygon.GetPolyPoints().Append( pcbnew.wxPoint( -halfsize, -halfsize ) + pos )
    #     polygon.GetPolyPoints().Append( pcbnew.wxPoint( -halfsize, halfsize ) + pos )
    #     #polygon.GetPolyShape().Append( halfsize+xPosition, halfsize+yPosition )
    #     #polygon.GetPolyShape().Append( halfsize+xPosition, -halfsize+yPosition )
    #     #polygon.GetPolyShape().Append( -halfsize+xPosition, -halfsize+yPosition )
    #     #polygon.GetPolyShape().Append( -halfsize+xPosition, halfsize+yPosition )
    #     return polygon

    # def _drawPixel(self, xPosition, yPosition):
    #     # build a rectangular pad as a dot on copper layer,
    #     # and a polygon (a square) on silkscreen
    #     if self.useCu:
    #         pad = pcbnew.D_PAD(self.module)
    #         pad.SetSize(pcbnew.wxSize(self.pxWidth, self.pxHeight))
    #         pad.SetPosition(pcbnew.wxPoint(xPosition, yPosition))
    #         pad.SetShape(pcbnew.PAD_SHAPE_RECT)
    #         pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    #         pad.SetName("")
    #         layerset = pcbnew.LSET()
    #         if self.onBack:
    #             layerset.AddLayer(pcbnew.B_Cu)
    #             layerset.AddLayer(pcbnew.B_Mask)
    #         else:
    #             layerset.AddLayer(pcbnew.F_Cu)
    #             layerset.AddLayer(pcbnew.F_Mask)
    #             pad.SetLayerSet( layerset )
    #         self.module.Add(pad)
    #     if self.useSilkS:
    #         if self.onBack:
    #             layer = pcbnew.B_SilkS
    #         else:
    #             layer = pcbnew.F_SilkS
    #     polygon = self.drawSquareArea(layer, self.pxWidth, xPosition, yPosition)
    #     self.module.Add(polygon)

    # def BuildThisFootprint(self):
    #     arrayToDraw = self.GetArrayToDraw()

    #     # used many times...
    #     # half_number_of_elements = arrayToDraw.__len__() / 2
    #     width = self.pixelsSource.getSize()[0]
    #     halfWidth = width / 2

    #     # Center position of image
    #     # yPosition = - int(half_number_of_elements * self.pxWidth)
    #     yPosition = 0

    #     for line in arrayToDraw:
    #         # xPosition = - int(half_number_of_elements * self.pxWidth)
    #         xPosition = 0
    #         for pixel in line:
    #             # Truth table for drawing a pixel
    #             # Negative is a boolean;
    #             # each pixel is a boolean (need to draw of not)
    #             # Negative | Pixel | Result
    #             #        0 |     0 | 0
    #             #        0 |     1 | 1
    #             #        1 |     0 | 1
    #             #        1 |     1 | 0
    #             # => Draw as Xor
    #             if self.negative != pixel: # Xor...
    #                 if self.onBack:
    #                     adjustedXPos = xPosition
    #                 else:
    #                     adjustedXPos = self.qr.modules.__len__() - xPosition
    #                 self._drawPixel(adjustedXPos, yPosition)
    #             xPosition += self.pxWidth
    #         yPosition += self.pxWidth

    #     #int((5 + half_number_of_elements) * self.pxWidth))
    #     textPosition = int((self.textHeight) + ((1 + halfWidth) * self.pxWidth))
    #     self.module.Value().SetTextHeight(self.textHeight)
    #     self.module.Value().SetTextWidth(self.textWidth)
    #     self.module.Value().SetThickness(self.textThickness)
    #     self.module.Reference().SetTextHeight(self.textHeight)
    #     self.module.Reference().SetTextWidth(self.textWidth)
    #     self.module.Reference().SetThickness(self.textThickness)
    #     if self.onBack:
    #         self.module.Value().Flip(pcbnew.wxPoint(0, 0))
    #         self.module.Reference().Flip(pcbnew.wxPoint(0, 0))
    #         textLayer = pcbnew.B_SilkS
    #     else:
    #         textLayer = pcbnew.F_SilkS
    #     self.module.Value().SetPosition(pcbnew.wxPoint(0, - textPosition))
    #     self.module.Reference().SetPosition(pcbnew.wxPoint(0, textPosition))
    #     self.module.Value().SetLayer(textLayer)

if __name__ != "__main__":
    # Run as a KiCad plugin
    QRCodeWizard().register()
