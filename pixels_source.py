'''
Defines an abstract class representing a black&white image.
'''

# SPDX-FileCopyrightText: 2021 Robin Vobruba <hoijui.quaero@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

class PixelsSource:
    '''
    Defines an abstract source of a rectangular image
    made up of black&white pixels.
    '''
    def getData(self) -> list:
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

    def getSize(self) -> (int, int):
        '''
        Returns the size of this image as (width, height).
        '''
        return (0, 0)

    def debug_to_stdout(self) -> None:
        '''
        Prints out this image as ASCII-art onto stdout,
        using '1' for black and ' ' for white.
        '''
        width = self.getSize()[0]
        lpi = 0
        for pixel in self.getData():
            if pixel == 0:
                pixel_char = ' '
            else:
                pixel_char = '1'
            print(pixel_char, end = '')
            lpi = lpi + 1
            lpi = lpi % width
            if lpi == 0:
                print()
