'''
How to generate a Sample QR-Code:
$ qrencode --structured --symversion 1 --size 1 --margin 1 --output qr.png "My Data"
$ # or the same in short:
$ qrencode -S -v 1 -s 1 -m 1 -o qr.png "My Data"
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
ID_PREFIX_QR_CODE = 'qr:'
ID_PREFIX_IMAGE = ''

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

def sign(x):
    if x == 0:
        return 0
    elif x < 0:
        return -1
    else:
        return 1

def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text

def ident2pixels_source(images_root, str):
    if str.startswith(ID_PREFIX_QR_CODE):
        qr_code_data = remove_prefix(str, ID_PREFIX_QR_CODE)
        ps = QrCodePixelsSource(qr_code_data)
    elif str.startswith(ID_PREFIX_IMAGE):
        image_path = remove_prefix(str, ID_PREFIX_IMAGE)
        ps = ImagePixelsSource(os.path.join(images_root, image_path))
    else:
        raise RuntimeError(f"Failed to creae PixelsSource from identifier '{str}'")
    return ps

class Placeholder:
    def __init__(self, board_element, top_left: (int, int), bottom_right: (int, int)):
        self.board_element = board_element
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.size_space = _minus(self.bottom_right, self.top_left)
        self.reverse = pcbnew.B_SilkS in self.board_element.GetLayerSet().Seq() or pcbnew.B_Cu in self.board_element.GetLayerSet().Seq()

    def isSilk(self):
        layers = self.board_element.GetLayerSet().Seq()
        return pcbnew.F_SilkS in layers or pcbnew.B_SilkS in layers

    def isCopper(self):
        return not self.isSilk()

    def isFront(self):
        return self.getLayer() in (pcbnew.F_Cu, pcbnew.F_SilkS)

    def isZone(self):
        return self.board_element.GetClass() == "ZONE_CONTAINER"

    def getLayer(self):
        for layer in self.board_element.GetLayerSet().Seq():
            if layer not in (pcbnew.F_Mask, pcbnew.B_Mask):
                return layer
        raise RuntimeError("No non-mask layer found!")


    def __eq__(self, other):
        return self.isCopper() == other.isCopper() and self.isFront() == other.isFront() and self.top_left == other.top_left and self.bottom_right == other.bottom_right and self.isZone() == other.isZone()

    def __lt__(self, other):
        diff = 0
        pot = 10
        diff = diff + (0 if self.isCopper() else 1) - (0 if other.isCopper() else 1) * 10^pot
        pot = pot - 1
        diff = diff + (0 if self.isFront() else 1) - (0 if other.isFront() else 1) * 10^pot
        pot = pot - 1
        diff = diff + sign(self.top_left[1] - other.top_left[1]) * 10^pot
        pot = pot - 1
        diff = diff + sign(self.top_left[0] - other.top_left[0]) * 10^pot
        pot = pot - 1
        diff = diff + sign(self.bottom_right[1] - other.bottom_right[1]) * 10^pot
        pot = pot - 1
        diff = diff + sign(self.bottom_right[0] - other.bottom_right[0]) * 10^pot
        pot = pot - 1
        diff = diff + (0 if self.isZone() else 1) - (0 if other.isZone() else 1) * 10^pot
        return diff < 0

    def __str__(self):
        return f'Placeholder[copper: {self.isCopper()}, front: {self.isFront()}, zone: {self.isZone()}, top-left: {self.top_left}, bottom-right: {self.bottom_right}]'

class Replacement:
    '''
    A single tempalte replacement in a KiCad PCB file.
    This keeps track of what to replace,
    and of *with* what to replace.
    '''
    def __init__(self, pcb, placeholder: Placeholder, pixels: PixelsSource, stretch: bool = False, negative: bool = False):
        self.pcb = pcb
        self.placeholder = placeholder
        self.stretch = stretch
        self.pixels = pixels
        self.negative = negative
        self.size_repl = self.pixels.getSize()
        self.size_pixel = self._calcPixelSize()
        self.first_pixel_pos = self._calcFirstPixelPos()

    def _calcPixelSize(self) -> (int, int):
        maxPixelSize = _div(self.placeholder.size_space, self.size_repl)
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
        border = _minus(self.placeholder.size_space, _mult(self.size_repl, self.size_pixel))
        border = _div(border, (2, 2))
        if self.placeholder.reverse:
            first_pixel_pos = (self.placeholder.bottom_right[0] - border[0], self.placeholder.top_left[1] + border[1])
        else:
            first_pixel_pos = self.placeholder.top_left + border
        return first_pixel_pos

    def _createAxisAlignedSilkRect(self, module: pcbnew.MODULE, pos: (int, int), size: (int, int)):
        # build a polygon (a square) on silkscreen
        # creates a EDGE_MODULE of polygon type. The polygon is a square
        polygon = pcbnew.EDGE_MODULE(module)
        polygon.SetShape(pcbnew.S_POLYGON)
        polygon.SetWidth(0)
        layer = self.placeholder.getLayer()
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
        if pcbnew.F_Cu in self.placeholder.board_element.GetLayerSet().Seq():
            layerset.AddLayer(pcbnew.F_Cu)
            layerset.AddLayer(pcbnew.F_Mask)
        else:
            layerset.AddLayer(pcbnew.B_Cu)
            layerset.AddLayer(pcbnew.B_Mask)
        #layerset = self.placeholder.GetLayerSet()
        pad.SetLayerSet(layerset)
        return pad

    def _drawPixel(self, module: pcbnew.MODULE, index: int, pos: (int, int)):
        # build a rectangular pad as a dot on copper layer,
        # and a polygon (a square) on silkscreen
        if self.placeholder.isSilk():
            pixel = self._createSilkPixel(module, index, pos)
        else:
            pixel = self._createCuPixel(module, index, pos)
        module.Add(pixel)

    def drawPixels(self):
        module = pcbnew.MODULE(self.pcb)
        module.SetDescription(f"Replaced template - {self.pixels}")
        module.SetLayer(self.placeholder.getLayer())

        if self.placeholder.isSilk():
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
                pos_adjust = (-(self.size_pixel[0] * (self.size_repl[0] - 1)), self.size_pixel[1])
            else:
                pos_adjust = (self.size_pixel[0], 0)
            if self.placeholder.reverse:
                pos_adjust = _mult((-1, 1), pos_adjust)
            pos = _plus(pos, pos_adjust)
        self.pcb.Add(module)

    def _drawCaption(self):
        # used many times...
        # half_number_of_elements = arrayToDraw.__len__() / 2
        width = self.pixels.getSize()[0]
        half_width = width / 2

        #int((5 + half_number_of_elements) * self.size_pixel[0]))
        text_pos = int((self.text_height) + ((1 + half_width) * self.size_pixel[0]))
        module = self.module

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

def replace_all_with(pcb, pixels_sources):
    placeholders = []

    for zone in pcb.Zones():
        poly_shape = zone.Outline()
        if poly_shape.OutlineCount() == 1 and poly_shape.VertexCount() == 4:
            try:
                (top_left, bottom_right) = extractCorners(zone, poly_shape)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            placeholder = Placeholder(zone, top_left, bottom_right)
            placeholders.append(placeholder)

    for drawing in pcb.GetDrawings():
        if drawing.GetClass() == "DRAWSEGMENT" and drawing.GetShape() == pcbnew.S_POLYGON and drawing.GetPointCount() == 4 and drawing.GetPolyShape().OutlineCount() == 1 and drawing.GetPolyShape().HoleCount(0) == 0:
            poly_shape = drawing.GetPolyShape()
            try:
                (top_left, bottom_right) = extractCorners(drawing, poly_shape)
            except RuntimeWarning as re:
                print("NOTE: %s" % re)
            placeholder = Placeholder(drawing, top_left, bottom_right)
            placeholders.append(placeholder)

    if len(pixels_sources) != len(placeholders):
        raise RuntimeError(f"{len(placeholders)} placeholders were found but {len(pixels_sources)} pixels-sources were supplied; they need to be the same amount!")

    # NOTE This uses Natural order for Placeholder objects, see Placeholder.__lt__(self, other)
    placeholders.sort()

    replacements = []
    phi = 0
    for psi in pixels_sources:
         replacements.append(Replacement(pcb, placeholders[phi], psi))
         phi = phi + 1

    for repl in replacements:
        repl.drawPixels()

    for repl in replacements:
        pcb.Remove(repl.placeholder.board_element)

def replace_all(pcb, images_root, pixels_sources_identifiers):
    pixels_sources = []
    for psi in pixels_sources_identifiers:
        ps = ident2pixels_source(images_root, psi)
        pixels_sources.append(ps)
    replace_all_with(pcb, pixels_sources)

@click.command()
@click.argument("repl_identifiers", type=click.STRING, nargs=-1)
@click.option('--input', '-i', type=click.Path(), required=1,
        default=None, help='Path to the input *.kicad_pcb file')
@click.option('--output', '-o', type=click.Path(),
        default=None, help='Output file path (default: input-REPLACED.kicad_pcb)')
@click.option('--images-root', '-r', type=click.Path(), envvar='IMAGES_ROOT',
        default=None, help='Where to resolve relative image paths to')
def replace_all_cli(repl_identifiers={}, input=None, output=None, images_root=None):
    """Replaces all QR-Code template polygons with the actual QR-Code image,
    both on the Copepr and Silkscreen layers,
    on the front and on the back, in a KiCad PCB file (*.kicad_pcb).

    KICAD_PCB_IN_FILE - The path to the `*.kicad_pcb` input file to replace QR-Code templates in
    KICAD_PCB_OUT_FILE - The path to the `*.kicad_pcb` output file
    """
    if output is None:
        output = R_KICAD_PCB_EXT.sub("-REPLACED.kicad_pcb", input)
    if images_root is None:
        images_root = os.curdir

    if input == output:
        raise RuntimeError("KiCad PCB input and output file names can not be the same!")

    pcb = pcbnew.LoadBoard(input)
    replace_all(pcb, images_root, repl_identifiers)
    pcbnew.SaveBoard(output, pcb)
    print(f"Written {output}!")

if __name__ == "__main__":
    # Run as a CLI script
    replace_all_cli()
