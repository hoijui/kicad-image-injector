'''
How to generate a Sample QR-Code:
$ qrencode --structured --symversion 1 --size 1 --margin 1 --output qrx.png "My Data"
$ # or the same in short:
$ qrencode -S -v 1 -s 1 -m 1 -o qrx.png "My Data"
'''
# TODO Document!!

# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re

import click
import pcbnew

from pixels_source import PixelsSource
from image_pixels_source import ImagePixelsSource
from qr_code_pixels_source import QrCodePixelsSource

# MIN_PIXEL_WIDTH = 0.5 * mm # TODO
MIN_PIXEL_WIDTH = 0.5 * 100000 # TODO Is this the correct multiplier
MIN_PIXEL_HEIGHT = MIN_PIXEL_WIDTH
R_KICAD_PCB_EXT = re.compile(r"\.kicad_pcb$")

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
    '''
    A single tempalte replacement in a KiCad PCB file.
    This keeps track of what to replace,
    and of *with* what to replace.
    '''
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
        pixel_i = 0
        x_i = 0
        for pixel in self.pixelsSource.getData():
            if (pixel != 0 and not self.negative) or (pixel == 0 and self.negative):
                self._drawPixel(module, pixel_i, pos)
            pixel_i = pixel_i + 1
            x_i = (x_i + 1) % self.sizeRepl[0]
            if x_i == 0:
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

        #int((5 + half_number_of_elements) * self.sizePixel[0]))
        textPosition = int((self.textHeight) + ((1 + halfWidth) * self.sizePixel[0]))
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
    x_s = set()
    y_s = set()
    for point_i in range(0, 4):
        point = polySet.CVertex(point_i)
        x_s.add(point.x)
        y_s.add(point.y)
    # Check if it is an axis-aligned rectangle
    if len(x_s) != 2 or len(y_s) != 2:
        raise RuntimeWarning("Not an axis-ligned rectangle: %s" % obj)
    topLeft = (min(x_s), min(y_s))
    bottomRight = (max(x_s), max(y_s))
    return (topLeft, bottomRight)

def replace_all(pcb, images_root):
    replacements = []

    for zone in pcb.Zones():
        pixels = zone.Outline()
        if pixels.OutlineCount() == 1 and pixels.VertexCount() == 4:
            try:
                (topLeft, bottomRight) = extractCorners(zone, pixels)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            pixelsSource = ImagePixelsSource("qrx.png") # HACK
            replacement = Replacement(pcb, zone, topLeft, bottomRight, pixelsSource)
            replacements.append(replacement)

    for drawing in pcb.GetDrawings():
        if drawing.GetClass() == "DRAWSEGMENT" and drawing.GetShape() == pcbnew.S_POLYGON and drawing.GetPointCount() == 4 and drawing.GetPolyShape().OutlineCount() == 1 and drawing.GetPolyShape().HoleCount(0) == 0:
            pixels = drawing.GetPolyShape()
            try:
                (topLeft, bottomRight) = extractCorners(drawing, pixels)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            pixelsSource = ImagePixelsSource("qrx.png") # HACK
            replacement = Replacement(pcb, drawing, topLeft, bottomRight, pixelsSource)
            replacements.append(replacement)

    for repl in replacements:
        repl._drawPixels()

    for repl in replacements:
        pcb.Remove(repl.placeholderDrawing)

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

if __name__ == "__main__":
    # Run as a CLI script
    replace_all_cli()
