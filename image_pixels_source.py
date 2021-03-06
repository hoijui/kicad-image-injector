'''
Defines a class representing a black&white image in a file.
'''

# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from PIL import Image

from pixels_source import PixelsSource

def load_as_binary_image(image_path):
    '''
    Loads a pixel image from a file,
    converting it to a binary one (== black&white),
    if it is not yet one.
    '''
    with Image.open(image_path) as img:
        if img.mode != "1":
            img = img.convert("L")
            img = img.convert("1")
        return img

class ImagePixelsSource(PixelsSource):
    '''
    Allows to use pixel image files as sources for black&white pixels.
    '''
    def __init__(self, image_path):
        self.image_path = image_path
        self.image = load_as_binary_image(image_path)

    def __str__(self):
        return f"Image-PixelsSource[path: '{self.image_path}']"

    def getSize(self):
        return self.image.size

    def getData(self):
        return self.image.getdata()

def testing():
    '''
    Testing - output to stdout.
    '''
    image_path = "qr.png"
    pixels = ImagePixelsSource(image_path)
    pixels.debug_to_stdout()

if __name__ == "__main__":
    testing()
