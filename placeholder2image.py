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
    def __init__(self, pcb, placeholder, top_left: int, bottom_right: int, pixels: PixelsSource, stretch: bool = False, negative: bool = False):
        self.pcb = pcb
        self.placeholder = placeholder
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.pixels = pixels
        self.stretch = stretch
        self.negative = negative
        self.size_space = _minus(self.bottom_right, self.top_left)
        self.size_repl = self.pixels.getSize()
        self.size_pixel = self._calcPixelSize()
        self.reverse = pcbnew.B_SilkS in self.placeholder.GetLayerSet().Seq() or pcbnew.B_Cu in self.placeholder.GetLayerSet().Seq()
        self.first_pixel_pos = self._calcFirstPixelPos()

    def _isSilk(self):
        layers = self.placeholder.GetLayerSet().Seq()
        return pcbnew.F_SilkS in layers or pcbnew.B_SilkS in layers

    def _getLayer(self):
        for layer in self.placeholder.GetLayerSet().Seq():
            if layer not in (pcbnew.F_Mask, pcbnew.B_Mask):
                return layer
        raise RuntimeError("No non-mask layer found!")

    def _calcPixelSize(self) -> (int, int):
        maxPixelSize = _div(self.size_space, self.size_repl)
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
        border = _minus(self.size_space, _mult(self.size_repl, self.size_pixel))
        border = _div(border, (2, 2))
        if self.reverse:
            first_pixel_pos = (self.bottom_right[0] - border[0], self.top_left[1] + border[1])
        else:
            first_pixel_pos = self.top_left + border
        return first_pixel_pos

    def _createAxisAlignedSilkRect(self, module: pcbnew.MODULE, pos: (int, int), size: (int, int)):
        # build a polygon (a square) on silkscreen
        # creates a EDGE_MODULE of polygon type. The polygon is a square
        polygon = pcbnew.EDGE_MODULE(module)
        polygon.SetShape(pcbnew.S_POLYGON)
        polygon.SetWidth(0)
        layer = self.placeholder.GetLayerSet().Seq()[0]
        polygon.SetLayer(layer)
        polygon.GetPolyShape().NewOutline()
        polygon.GetPolyShape().Append(pos[0] + size[0], pos[1] + size[1])
        polygon.GetPolyShape().Append(pos[0] + size[0], pos[1])
        polygon.GetPolyShape().Append(pos[0], pos[1])
        polygon.GetPolyShape().Append(pos[0], pos[1] + size[1])
        return polygon

    def _createSilkPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        return self._createAxisAlignedSilkRect(module, pos, self.size_pixel)

    def _createCuPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        # build a rectangular pad as a dot on copper layer,
        pad = pcbnew.D_PAD(module)
        pad.SetSize(pcbnew.wxSize(self.size_pixel[0], self.size_pixel[1]))
        pad.SetPosition(pcbnew.wxPoint(pos[0], pos[1]))
        pad.SetLocalCoord()
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetName("")
        layerset = pcbnew.LSET()
        if pcbnew.F_Cu in self.placeholder.GetLayerSet().Seq():
            layerset.AddLayer(pcbnew.F_Cu)
            layerset.AddLayer(pcbnew.F_Mask)
        else:
            layerset.AddLayer(pcbnew.B_Cu)
            layerset.AddLayer(pcbnew.B_Mask)
        # layerset = self.placeholder.GetLayerSet()
        pad.SetLayerSet(layerset)
        return pad

    def _drawPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        # build a rectangular pad as a dot on copper layer,
        # and a polygon (a square) on silkscreen
        if self._isSilk():
            pixel = self._createSilkPixel(module, index, pos)
        else:
            pixel = self._createCuPixel(module, index, pos)
        module.Add(pixel)

    def drawPixels(self):
        module = pcbnew.MODULE(self.pcb)
        module.SetDescription("Replaced template - ... - TODO") # TODO Use this for meta-data, eg. replacement image path
        module.SetLayer(self._getLayer())

        if self._isSilk():
            module.SetPosition(pcbnew.wxPoint(self.first_pixel_pos[0], self.first_pixel_pos[1]))
            pos = (0, 0)
        else:
            pos = self.first_pixel_pos
        pixel_i = 0
        x_i = 0
        for pixel in self.pixels.getData():
            if (pixel != 0 and not self.negative) or (pixel == 0 and self.negative):
                self._drawPixel(module, pixel_i, pos)
            pixel_i = pixel_i + 1
            x_i = (x_i + 1) % self.size_repl[0]
            if x_i == 0:
                pos_adjust = (-(self.size_pixel[0] * (self.size_repl[0] - 1)),
                              self.size_pixel[1])
            else:
                pos_adjust = (self.size_pixel[0], 0)
            if self.reverse:
                pos_adjust = _mult((-1, 1), pos_adjust)
            pos = _plus(pos, pos_adjust)
        #module.Add(self._createAxisAlignedSilkRect(module, (0, 0), (168402000, 168402000))) # HACK Just draw a huge rect, to see if it is visible -> Yes it is! :-)
        self.pcb.Add(module)

    def _drawCaption(self):
        # used many times...
        # half_number_of_elements = arrayToDraw.__len__() / 2
        width = self.pixels.getSize()[0]
        half_width = width / 2

        #int((5 + half_number_of_elements) * self.size_pixel[0]))
        text_pos = int((self.textHeight) + ((1 + half_width) * self.size_pixel[0]))
        module = self.placeholder.GetParent()

        module.Value().SetTextHeight(self.text_height)
        module.Value().SetTextWidth(self.text_width)
        module.Value().SetThickness(self.text_thickness)
        module.Reference().SetTextHeight(self.text_height)
        module.Reference().SetTextWidth(self.text_width)
        module.Reference().SetThickness(self.text_thickness)
        if self.reverse:
            module.Value().Flip(pcbnew.wxPoint(0, 0))
            module.Reference().Flip(pcbnew.wxPoint(0, 0))
            text_layer = pcbnew.B_SilkS
        else:
            text_layer = pcbnew.F_SilkS
        module.Value().SetPosition(pcbnew.wxPoint(0, - text_pos))
        module.Reference().SetPosition(pcbnew.wxPoint(0, text_pos))
        module.Value().SetLayer(text_layer)

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
    top_left = (min(x_s), min(y_s))
    bottom_right = (max(x_s), max(y_s))
    return (top_left, bottom_right)

def replace_all(pcb, images_root):
    replacements = []

    for zone in pcb.Zones():
        pixels = zone.Outline()
        if pixels.OutlineCount() == 1 and pixels.VertexCount() == 4:
            try:
                (top_left, bottom_right) = extractCorners(zone, pixels)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            pixels = ImagePixelsSource(os.path.join(images_root, "qrx.png")) # HACK
            replacement = Replacement(pcb, zone, top_left, bottom_right, pixels)
            replacements.append(replacement)

    for drawing in pcb.GetDrawings():
        if drawing.GetClass() == "DRAWSEGMENT" and drawing.GetShape() == pcbnew.S_POLYGON and drawing.GetPointCount() == 4 and drawing.GetPolyShape().OutlineCount() == 1 and drawing.GetPolyShape().HoleCount(0) == 0:
            pixels = drawing.GetPolyShape()
            try:
                (top_left, bottom_right) = extractCorners(drawing, pixels)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            pixels = ImagePixelsSource("qrx.png") # HACK
            replacement = Replacement(pcb, drawing, top_left, bottom_right,
                                      pixels)
            replacements.append(replacement)

    for repl in replacements:
        repl.drawPixels()

    for repl in replacements:
        pcb.Remove(repl.placeholder)

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
