'''
Defines a class representing a black&white text string.
'''

# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from PIL import Image, ImageFont, ImageDraw, ImageEnhance

from pixels_source import PixelsSource

_FONT = ImageFont.truetype(font="LiberationSerif-Regular", size=30)

class StringPixelsSource(PixelsSource):
    '''
    Allows to use a string as source for black&white pixels.
    '''
    def __init__(self, text: str):
        self.text = text
        text_size = _FONT.getsize(text)
        image_size = (text_size[0] + 2, text_size[1] + 2)
        self.image = Image.new("RGBA", image_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.image)
        draw.rectangle(((0, 0), image_size), fill="white")
        draw.rectangle(((1, 1), text_size), fill="black")
        draw.text((1, -1), text, font=_FONT, spaceing=1)
        self.image = self.image.convert("L")
        self.image = self.image.convert("1")

    def __str__(self):
        return f"String-PixelsSource[text: '{self.text}']"

    def getSize(self):
        return self.image.size

    def getData(self):
        return self.image.getdata()

def testing():
    '''
    Testing - output to stdout.
    '''
    number = 99
    text = str(number)
    pixels = StringPixelsSource(text)
    pixels.debug_to_stdout()

if __name__ == "__main__":
    testing()
