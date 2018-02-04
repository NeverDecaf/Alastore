#!/usr/bin/python
'''This has been slightly modified from the original.
I believe there was an error that caused the icons to become random noise.
It is likely the fix only works for icons of exactly size 256x256
'''
# pyico
# Copyright (C) 2009  Nikolai Ugelvik
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA






import sys
import struct
import math

from PIL import Image


class Icon(object):
    def __init__(self, image_paths=None, output_path=None):
        self.image_paths = []
        if image_paths:
            self.image_paths = image_paths
        self.output_path = None
        if output_path:
            self.output_path = output_path

        self._ico_data = ""
        self._img_data = ""

        # Conversion info
        self._convert_rgb = False

    def convert_rgb(self, boolean):
        self._convert_rgb = boolean

    def getdata(self):
        return self._ico_data + self._img_data

    def save(self):
        if not self._ico_data or not self._img_data:
            self._build()

        if self.output_path:
            with open(self.output_path, 'wb') as f:
                f.write(self._ico_data)
                f.write(self._img_data)
        else:
            raise Exception("Missing output path.")

    def __load_image(self, image_path):
        img = Image.open(image_path)
        img.load() # fix for a bug in PIL 1.1.7

        if self._convert_rgb:
            if 'A' in img.mode or 'transparency' in img.info:
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')

        if img.mode == 'RGB':
            imgdata = img.tobytes('raw', 'BGR', 0, -1)
        elif img.mode == 'RGBA':
            r, g, b, a = img.split()
            img = Image.merge('RGBA', (b, g, r, a))
            imgdata = img.tobytes('raw', 'RGBA', 0, -1)
        elif img.mode == 'P':
            imgdata = img.tobytes('raw', 'P', 0, -1)

        return (img, imgdata)

    def _build(self):
        self._ico_data = ""
        self._img_data = b""

        if not len(self.image_paths):
            raise Exception("No images added")

        num_images = len(self.image_paths)

        self._ico_data = self._generate_header(num_images)

        # Size of all the headers (image headers + file header)
        dataoffset = struct.calcsize('BBBBHHII') * num_images + \
                struct.calcsize('HHH')
        
        for image in self.image_paths:
            icondirentry, imgdata, dataoffset = self._generate_icondirentry(
                    image, dataoffset)
            self._ico_data += icondirentry
            self._img_data += imgdata

        if self.output_path:
            self.save()

    def _calcstride(self, width_in_bits):
##        length = (width_in_bits + 31) // 32
##        return length * 4
        return width_in_bits*4

    def _generate_header(self, num_images):
        return struct.pack('HHH', 0, 1, num_images)


    def _generate_icondirentry(self, image_path, dataoffset):
        img, imgdata = self.__load_image(image_path)

        bWidth = img.size[0]
        bHeight = img.size[1]
        bReserved = 0
        wPlanes = 0

        # Bit count
        if img.mode == 'RGB':
            wBitCount = 24
            bColorCount = 0 
        elif img.mode == 'RGBA':
            wBitCount = 32
            bColorCount = 0
        elif img.mode == 'P':
            wBitCount = 8
            bColorCount = len(img.palette.getdata()[1]) // 3
            print(bColorCount)

        dwImageOffset = dataoffset

        # Num bytes in image section
        length = len(imgdata) + self._calcstride(img.size[0]) * img.size[1]
        
        # Generate bitmapinfoheader and prepend this to the pixel data
        bmpinfoheader = self._generate_bitmapinfoheader(bWidth, bHeight, wPlanes, 
                wBitCount, length, bColorCount)

        data = bmpinfoheader
        if img.mode == 'RGB' or img.mode == 'RGBA':
            # XOR mask (Image)
            data += imgdata
            palette_alpha = False
        elif img.mode == 'P':
            # Write the palette
            palette_data = img.palette.getdata()
            if palette_data[0] == 'RGB;L' or palette_data[0] == 'RGB':
                palette_alpha = False
                for x in range(0, len(palette_data[1]), 3):
                    data += palette_data[1][x + 2] # B
                    data += palette_data[1][x + 1] # G
                    data += palette_data[1][x]     # R 
                    data += struct.pack('B', 0)
                data += imgdata
            elif palette_data[0] == 'RGBA;L' or palette_data[0] == 'RGBA':
                palette_alpha = True
                #for x in range(4): data += struct.pack('B', 0)
                for x in range(0, len(palette_data[1]), 3):
                    data += palette_data[1][x + 2] # B
                    data += palette_data[1][x + 1] # G
                    data += palette_data[1][x]     # R 
                    data += struct.pack('B', 0)
                for byte in imgdata:
                    if ord(byte) == 0:
                        data += struct.pack('B', 0)
                    else:
                        data += struct.pack('B', ord(byte))

        # AND mask (Transparency)
        if not palette_alpha:
            rowstride = self._calcstride(img.size[0])
##            print("rowstride", rowstride)
            data += struct.pack('B', 0) * (rowstride * img.size[1])
        else:
            rowstride = self._calcstride(img.size[0])
##            print("rowstride", rowstride)
            bytes = [0 for x in range(rowstride * img.size[1])]
            for y in range(img.size[1] - 1, -1, -1):
                for x in range(img.size[0]):
                    i = (y * rowstride + x // 8)
                    if img.getpixel((x, y)) == 0:
                        bytes[i] = bytes[i] | 2**(7 - x % 8)
            for y in range(img.size[1] - 1, -1, -1):
                for x in range(rowstride):
                    data += struct.pack('B', bytes[y * rowstride + x])

        # Increment the data offset pointer
        dataoffset += len(data)

        # Size of the dir entry + image data
        dwBytesInRes = len(data)
        
        # Pack the icondirentry header
##        print bWidth, bHeight, bColorCount, bReserved,\
##        wPlanes, wBitCount,\
##                dwBytesInRes, dwImageOffset
        icondirentry = struct.pack('BBBBHHII',
                bWidth%256, bHeight%256, bColorCount, bReserved, wPlanes, wBitCount,
                dwBytesInRes, dwImageOffset)
        
        return icondirentry, data, dataoffset

    def _generate_bitmapinfoheader(self, width, height, planes, bit_count, size_image, colors_used):
        # BitmapInfoHeader
        biSize = struct.calcsize('IIIHHIIiiII')
        biWidth = width
        biHeight = height * 2 # Include the mask height
        biPlanes = 1 # Must be 1
        biBitCount = bit_count
        biCompression = 0
        biSizeImage = size_image
        biXPelsPerMeter = 0
        biYPelsPerMeter = 0
        biClrUsed = colors_used
        biClrImportant = 0

        return struct.pack('IIIHHIIiiII', biSize, biWidth, biHeight, biPlanes,
                biBitCount, biCompression, biSizeImage, biXPelsPerMeter,
                biYPelsPerMeter, biClrUsed, biClrImportant)


if __name__ == '__main__':
    import sys
    from optparse import OptionParser

    usage = "usage: %prog [options] file1 file2 ..."
    parser = OptionParser(usage=usage)
    parser.add_option("-o", "--output", dest="output_file",
            help="Write the icon to this file")
    parser.add_option("-c", "--convert-rgb", dest="convert_rgb",
            action="store_true", default=False,
            help="Convert images to RGB or RGBA (if the image has alpha)"
            " format before writing.")
    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.print_help()
        sys.stderr.write("\nNo input images specified. Exiting.\n")
        sys.exit(1)
    if not options.output_file:
        sys.stderr.write("\nNo output file specified. Exiting.\n")
        sys.exit(2)

    ico = Icon(args, options.output_file)
    if options.convert_rgb:
        ico.convert_rgb(True)
    ico.save()

    print("Successfully wrote icon to %s." % options.output_file)

