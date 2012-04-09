import hashlib
import math
import os
import re
import shutil
import subprocess

from django.utils.encoding import smart_str

import mediagenerator.settings as settings
from mediagenerator import utils
from mediagenerator.generators.bundles.base import Filter, FileFilter
from mediagenerator.utils import get_media_dirs
from mediagenerator.settings import GENERATED_MEDIA_DIR

def _find_root(name):
    for root in get_media_dirs():
        sprite_root = os.path.join(root, re.sub(".sprite$", "", name))
        if os.path.isdir(sprite_root):
            return sprite_root
    
    raise Exception("No sprite dirrectory found %s" % name)

class Sprite(Filter):
    
    dev_mimetype = "text/css"
    
    def __init__(self, **kwargs):
        self.config(kwargs)
        super(Sprite, self).__init__(**kwargs)
        self.file_filter = SpriteFile

    def get_output(self, variation):
        yield '\n\n'.join(input for input in self.get_input(variation))

    

class SpriteFile(FileFilter):
    
    
    def get_dev_output(self, name, variation):
        css = SpriteBuilder(re.sub("\.sprite$", "", self.name))
        return css.render()

    def get_dev_output_names(self, variation):
        sprite_root = _find_root(self.name)
        yield self.name + ".css", str(os.path.getmtime(sprite_root))


class ImgInfo(object):
   
    # Example info string:
    # airport.png PNG 30x35 30x35+0+0 8-bit DirectClass 1.8KB 0.080u 0:00.010
    IMG_INFO_RE = re.compile("^(.+?)(\[\d+\])? PNG (\d+x\d+)")

    @classmethod
    def from_string(cls, info):
        m = cls.IMG_INFO_RE.match(info)
        if not m: 
            return False

        name = m.group(1)
        size = m.group(3).split("x")
        size = int(size[0]), int(size[1])
        return cls(name, size)

    def __init__(self, name, size):
        self.name = name
        self.size = size
        self.offset = 0, 0

    def calc_offset(self, img=None):
        if img:
            self.offset = 0, img.offset[1] - img.size[1]

        
        
        

class SpriteBuilder(object):
    CSS_NAME_RE = re.compile("\.png$|[^a-zA-z0-9\-_]")
    """
    Builds sprite and render css.
    In debug mode just collect info from images.
    In production mode generates single image.
    If sprites are located at img/sprite/icons/*.png:
        self.name => img/sprite/icons
        self.collection => icons
        self.root => /home/username/djangoprogect/static/img/sprite/icons
        self.generated_filename => (only in production mode)
            /home/username/djangoprogect/_generate_media/img/sprite/icons-XXXXXXXXXXXX.png
        self.images => info about found images
    """
    def __init__(self, name):
        self.css = []
        self.debug = settings.MEDIA_DEV_MODE
        self.name = name
        self.root = _find_root(name)
        self.tmpfiles = []
        self.collection = self.CSS_NAME_RE.sub("", os.path.split(self.name)[-1])
        self.generated_filename, self.images = self._generate_images()
        
        bg_w = 0
        bg_h = 0
        for i in self.images:
            w, h = i.size
            bg_w = max(bg_w, w)
            bg_h += h
        self.bgimg_info = ImgInfo(self.generated_filename, (bg_w, bg_h))

    def handle_sprite(self, img, with_headers=True, bgimage=False, scale=1.0):

        custom_class = ".spr-%s.%s" % (self.collection,
            self.CSS_NAME_RE.sub("", img.name)
        )

        if self.debug:
            bg_style = "background: transparent url('%s/%s/%s') no-repeat" % (
                settings.DEV_MEDIA_URL.rstrip("/"), 
                self.name,
                img.name
            )
        else:
            if bgimage:
                bg_style = "background: transparent url('%s') no-repeat %dpx %dpx" % (
                    bgimage.name,
                    math.floor(img.offset[0] * scale),
                    math.floor(img.offset[1] * scale)
                )
            else:
                bg_style = "background-position: %dpx %dpx" % img.offset


        css_entry = ""
        if with_headers: css_entry +=  "%s { " % custom_class
        css_entry += "width: %dpx; height: %dpx; " % tuple([math.floor(x*scale) for x in img.size])
        css_entry += "%s; " % bg_style
        if bgimage:
            scaled_size = tuple([math.floor(x*scale) for x in bgimage.size])
            css_entry += "-webkit-background-size: %dpx %dpx; " % scaled_size
            css_entry += "background-size: %dpx %dpx; " % scaled_size

        if with_headers: css_entry += "}"

        return css_entry

    def render(self):
        """
        Rendnder compleate css for bundle-based inclusion
        """
        css = []
        if not self.debug:
            top_css = ".spr-%s { background: transparent url('%s') no-repeat; }" % (
                self.collection,
                self.generated_filename
            )
            css.append(top_css)

        for img in self.images:
            css_entry = self.handle_sprite(img)
            css.append(css_entry)

        return "\n".join(css)

    def render_include(self, imgname, scale=1.0):
        """
        Render single css entry for css-based inclusion
        """
        img = None
        for i in self.images:
            if i.name == imgname:
                img = i
                break

        if not img:
            raise Exception("Sprite not found at '%s/%s'" % (self.root, imgname))

        if self.debug:
            bgimg_name = "%s/%s" % (self.name, imgname)
            bgimg = ImgInfo(bgimg_name, img.size)
        else:
            bgimg = self.bgimg_info

        return self.handle_sprite(img, with_headers=False, bgimage=bgimg, scale=scale)

    
    _dbg_images_cache   = {}
    _pub_images_cache   = {}
    _pub_generated_file = {}
    def _generate_images(self):
        if self.debug and self.name in self._dbg_images_cache:
            result, mtime = self._dbg_images_cache[self.name]
            if os.path.getmtime(self.root) == mtime:
                return "", result

        if not self.debug and self.name in self._pub_images_cache:
            return self._pub_generated_file[self.name], self._pub_images_cache[self.name]

        generated_filename = ""
        return_path = os.path.abspath(".")
        os.chdir(os.path.join(self.root))
        if self.debug:
            # Use convert instead identify here becouse identify throws 
            # errors on older ImageMagic version (no errors found on ubuntu 11.10).
            # *cmd* called once per folder so there is shouldn't be lot of 
            # performance lost in dev mode
            cmd = ["convert", "-identify", "-strip", "-append", "*.png", "/dev/null" ]
        else:
            tmpfilename = "../%s.png" % self.collection
            cmd = ["convert", "-identify", "-strip", "-append", "*.png", tmpfilename ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        procout, procerr = proc.communicate()
        if proc.returncode != 0:
            raise Exception("Unable to join sprites or get info: %s" % procout)

        if not self.debug:
            with open(tmpfilename, "r") as sf:
                version = hashlib.sha1(smart_str(sf.read())).hexdigest()

            self.tmpfiles.append(os.path.abspath(tmpfilename))
            generated_key = "%s.png" % self.name
            generated_value = "%s-%s.png" % (self.name, version)
            generated_filename = "%s/%s" % (settings.PRODUCTION_MEDIA_URL.rstrip("/"), generated_value)
            utils.NAMES[generated_key] = generated_value
            self._pub_generated_file[self.name] = generated_filename
            copy_to = os.path.join(GENERATED_MEDIA_DIR, *os.path.split(self.name)[:-1])
            copy_to = os.path.join(copy_to, "%s-%s.png" % (self.collection, version))
            shutil.copyfile(tmpfilename, copy_to)

        os.chdir(return_path)
        last_img = None
        result = []
        for imginfo in procout.split("\n"):
            img = ImgInfo.from_string(imginfo)
            if img:
                img.calc_offset(last_img)
                last_img = img
                result.append(img)

        if self.debug:
            self._dbg_images_cache[self.name] = result, os.path.getmtime(self.root)
        else:
            self._pub_images_cache[self.name] = result

        return generated_filename, result

    def __del__(self):
        for f in self.tmpfiles:
            os.remove(f)

class CSSSprite(FileFilter):
    """ process @include sprite('/path/to/sprite') """

    rewrite_re = re.compile("@include sprite\(\s*[\"']([0-9a-zA-Z/_\.\-]+?)['\"]?\s*(,\s*([\d\.]+)\s*)?\)\s*;?", re.UNICODE)
    rewrite_re_depricated = re.compile("@import sprite\(\s*[\"']([0-9a-zA-Z/_\.\-]+?)['\"]?\s*(,\s*([\d\.]+)\s*)?\)\s*;?", re.UNICODE)
    all_import_re = re.compile("@import allsprites\(\s*[\"']/*([a-zA-Z/_\.\-]+?)/*['\"]?\s*\)\s*;?", re.UNICODE)
    def __init__(self, **kwargs):
        super(CSSSprite, self).__init__(**kwargs)
        assert self.filetype == 'css', (
            'CSSSprite only supports CSS output. '
            'The parent filter expects "%s".' % self.filetype)

    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(CSSSprite, self).get_dev_output(name, variation)

        content = self.all_import_re.sub(self.make_imports_all, content)
        content = self.rewrite_re_depricated.sub(self.warn_imports, content)
        return self.rewrite_re.sub(self.make_imports, content)

    def make_imports_all(self, match):
        sprite_name = match.group(1)
        css = SpriteBuilder(sprite_name)
        return css.render()

    def warn_imports(self, match):
        info = self.name, match.string.count('\n', 0, match.start())
        print "[%s:%d] `@import sprite()` is depricated, use @include sprite instead." % info
        return self.make_imports(match)

    def make_imports(self, match):
        fname = match.group(1)
        scale = match.group(3) and float(match.group(3)) or 1.0
        split_path = os.path.split(fname)
        sprite_file = split_path[-1]
        sprite_name = os.path.join(split_path[:-1])[0].lstrip('/') 
        css = SpriteBuilder(sprite_name.rstrip("/"))
        return css.render_include(sprite_file, scale)
