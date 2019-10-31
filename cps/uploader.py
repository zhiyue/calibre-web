#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2012-2019 lemmsh cervinko Kennyl matthazinski OzzieIsaacs
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

from __future__ import division, print_function, unicode_literals
import os
import hashlib
import struct
from tempfile import gettempdir

from . import logger, comic
from .constants import BookMeta


log = logger.create()


try:
    from lxml.etree import LXML_VERSION as lxmlversion
except ImportError:
    lxmlversion = None

try:
    from wand.image import Image
    from wand import version as ImageVersion
    from wand.exceptions import PolicyError
    use_generic_pdf_cover = False
except (ImportError, RuntimeError) as e:
    log.debug('cannot import Image, generating pdf covers for pdf uploads will not work: %s', e)
    use_generic_pdf_cover = True

try:
    from . import minecart
    #from PyPDF4 import PdfFileReader
    # from PyPDF4 import __version__ as PyPdfVersion
    use_pdf_meta = True
except ImportError as e:
    log.debug('cannot import PyPDF2, extracting pdf metadata will not work: %s', e)
    use_pdf_meta = False

try:
    from . import epub
    use_epub_meta = True
except ImportError as e:
    log.debug('cannot import epub, extracting epub metadata will not work: %s', e)
    use_epub_meta = False

try:
    from . import fb2
    use_fb2_meta = True
except ImportError as e:
    log.debug('cannot import fb2, extracting fb2 metadata will not work: %s', e)
    use_fb2_meta = False

try:
    from PIL import Image as PILImage
    from PIL import ImageOps
    from PIL import __version__ as PILversion
    use_PIL = True
except ImportError as e:
    log.debug('cannot import Pillow, using png and webp images as cover will not work: %s', e)
    use_generic_pdf_cover = True
    use_PIL = False



__author__ = 'lemmsh'


def process(tmp_file_path, original_file_name, original_file_extension):
    meta = None
    try:
        if ".PDF" == original_file_extension.upper():
            meta = pdf_meta(tmp_file_path, original_file_name, original_file_extension)
        if ".EPUB" == original_file_extension.upper() and use_epub_meta is True:
            meta = epub.get_epub_info(tmp_file_path, original_file_name, original_file_extension)
        if ".FB2" == original_file_extension.upper() and use_fb2_meta is True:
            meta = fb2.get_fb2_info(tmp_file_path, original_file_extension)
        if original_file_extension.upper() in ['.CBZ', '.CBT']:
            meta = comic.get_comic_info(tmp_file_path, original_file_name, original_file_extension)

    except Exception as ex:
        log.warning('cannot parse metadata, using default: %s', ex)

    if meta and meta.title.strip() and meta.author.strip():
        return meta
    else:
        return default_meta(tmp_file_path, original_file_name, original_file_extension)


def default_meta(tmp_file_path, original_file_name, original_file_extension):
    return BookMeta(
        file_path=tmp_file_path,
        extension=original_file_extension,
        title=original_file_name,
        author=u"Unknown",
        cover=None,
        description="",
        tags="",
        series="",
        series_id="",
        languages="")


def pdf_meta(tmp_file_path, original_file_name, original_file_extension):

    if use_pdf_meta:
        pdf = minecart.Document(open(tmp_file_path, 'rb'))
        doc_info = pdf.getDocumentInfo()
    else:
        pdf = None
        doc_info = None

    if doc_info is not None:
        author = doc_info['author'] if 'author' in doc_info else u"Unknown"
        title = doc_info['title'] if 'title' in doc_info else original_file_name
        subject = doc_info['subject'] if 'subject' in doc_info else ""
    else:
        author = u"Unknown"
        title = original_file_name
        subject = ""
    return BookMeta(
        file_path=tmp_file_path,
        extension=original_file_extension,
        title=title,
        author=author,
        cover=pdf_preview(pdf, tmp_file_path, original_file_name),
        description=subject,
        tags="",
        series="",
        series_id="",
        languages="")


def pdf_preview(doc, tmp_file_path, tmp_dir):
    if use_generic_pdf_cover:
        return None
    else:
        if use_PIL and use_pdf_meta:
            try:
                page = doc.get_page(0)
                if len(page.images) == 1:
                    bbox = page.images[0].bbox
                    im = page.images[0].as_pil()
                    mediaBox = page.media_box
                    box = page.crop_box
                    width = im.width
                    height = im.height
                    if box != mediaBox:
                        im = im.crop((box[0] / mediaBox[2] * width,
                                      box[1] / mediaBox[3] * height,
                                      box[2] / mediaBox[2] * width,
                                      box[3] / mediaBox[3] * height))

                    pos_size=(int(bbox[2]-bbox[0]),int(bbox[3]-bbox[1]))
                    if pos_size != (im.width, im.height):
                        im = im.resize(pos_size, PILImage.ANTIALIAS)
                    left_top = (int(bbox[0]), int(bbox[1]))
                    if left_top != (0,0):
                        canvas = PILImage.new('RGB', (int(mediaBox[2]), int(mediaBox[3])), color=(255, 255, 255, 0))
                        canvas.paste(im, left_top)
                    else:
                        canvas = im
                    cords = page.images[0].ctm
                    if cords[0] - cords[1] < 0:
                        canvas = canvas.transpose(PILImage.FLIP_LEFT_RIGHT)
                    if cords[3] - cords[2] < 0:
                        canvas = canvas.transpose(PILImage.FLIP_TOP_BOTTOM)

                    cover_file_name = os.path.splitext(tmp_file_path)[0] + ".cover.jpg"
                    # ToDo: DPI and resolution
                    canvas.info['dpi'] = (150, 150)
                    canvas.save(cover_file_name, dpi=(150,150))
                    # canvas.save(cover_file_name)
                    return cover_file_name
            except Exception as ex:
                log.exception(ex)
                print(ex)

        try:
            cover_file_name = os.path.splitext(tmp_file_path)[0] + ".cover.jpg"
            with Image(filename=tmp_file_path + "[0]", resolution=150) as img:
                img.compression_quality = 88
                img.save(filename=os.path.join(tmp_dir, cover_file_name))
            return cover_file_name
        except PolicyError as ex:
            log.warning('Pdf extraction forbidden by Imagemagick policy: %s', ex)
            return None
        except Exception as ex:
            log.warning('Cannot extract cover image, using default: %s', ex)
            return None


def get_versions():
    if not use_generic_pdf_cover:
        IVersion = ImageVersion.MAGICK_VERSION
        WVersion = ImageVersion.VERSION
    else:
        IVersion = u'not installed'
        WVersion = u'not installed'
    if use_pdf_meta:
        # PVersion='v'+PyPdfVersion
        PVersion = u'installed'
    else:
        PVersion=u'not installed'
    if lxmlversion:
        XVersion = 'v'+'.'.join(map(str, lxmlversion))
    else:
        XVersion = u'not installed'
    if use_PIL:
        PILVersion = 'v' + PILversion
    else:
        PILVersion = u'not installed'
    if comic.use_comic_meta:
        ComicVersion = u'installed'
    else:
        ComicVersion = u'not installed'
    return {'Image Magick': IVersion,
            'PyPdf': PVersion,
            'lxml':XVersion,
            'Wand': WVersion,
            'Pillow': PILVersion,
            'Comic_API': ComicVersion}


def upload(uploadfile):
    tmp_dir = os.path.join(gettempdir(), 'calibre_web')

    if not os.path.isdir(tmp_dir):
        os.mkdir(tmp_dir)

    filename = uploadfile.filename
    filename_root, file_extension = os.path.splitext(filename)
    md5 = hashlib.md5()
    md5.update(filename.encode('utf-8'))
    tmp_file_path = os.path.join(tmp_dir, md5.hexdigest())
    uploadfile.save(tmp_file_path)
    meta = process(tmp_file_path, filename_root, file_extension)
    return meta
