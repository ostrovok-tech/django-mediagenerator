import hashlib
import os
import random
import re
import shutil
import subprocess

from django.utils.encoding import smart_str

import mediagenerator.settings as settings
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

    def handle_sprite(self, img, with_headers=True, force_bgimage=False):

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
            if force_bgimage:
                bg_style = "background: transparent url('%s') no-repeat %dpx %dpx" % (
                    force_bgimage,
                    img.offset[0],
                    img.offset[1]
                )
            else:
                bg_style = "background-position: %dpx %dpx" % img.offset


        css_entry = ""
        if with_headers: css_entry +=  "%s { " % custom_class
        css_entry += "width: %dpx; height: %dpx; " % img.size
        css_entry += "%s; " % bg_style
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

    def render_include(self, imgname):
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
            force_bgimage = "%s/%s" % (self.name, imgname)
        else:
            force_bgimage = self.generated_filename

        return self.handle_sprite(img, with_headers=False, force_bgimage=force_bgimage)

    
    _dbg_images_cache   = {}
    _pub_images_cache   = {}
    _pub_generated_file = {}
    def _generate_images(self):
        if self.debug and self.name in self._dbg_images_cache:
            return "", self._dbg_images_cache[self.name]

        if not self.debug and self.name in self._pub_images_cache:
            return self._pub_generated_file[self.name], self._pub_images_cache[self.name]

        generated_filename = ""
        return_path = os.path.abspath(".")
        os.chdir(os.path.join(self.root))
        if self.debug:
            cmd = ["identify", "*.png"]
        else:
            tmpfilename = "../%s.png" % self.collection
            cmd = ["convert", "-identify", "-strip", "-append", "*.png", tmpfilename ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        proc.wait()
        if proc.returncode != 0:
            raise Exception("Unable to join sprites or get info: %s" % proc.stdout.read())

        if not self.debug:
            with open(tmpfilename, "r") as sf:
                version = hashlib.sha1(smart_str(sf.read())).hexdigest()

            self.tmpfiles.append(os.path.abspath(tmpfilename))
            generated_filename = "%s/%s/%s-%s.png" % (
                settings.PRODUCTION_MEDIA_URL.rstrip("/"),
                "/".join(self.name.split("/")[:-1]), 
                self.collection,
                version
            )
            self._pub_generated_file[self.name] = generated_filename
            copy_to = os.path.join(GENERATED_MEDIA_DIR, *os.path.split(self.name)[:-1])
            copy_to = os.path.join(copy_to, "%s-%s.png" % (self.collection, version))
            shutil.copyfile(tmpfilename, copy_to)

        os.chdir(return_path)
        last_img = None
        result = []
        for imginfo in proc.stdout.read().split("\n"):
            img = ImgInfo.from_string(imginfo)
            if img:
                img.calc_offset(last_img)
                last_img = img
                result.append(img)

        if self.debug:
            self._dbg_images_cache[self.name] = result
        else:
            self._pub_generated_file[self.name] = result

        return generated_filename, result

    def __del__(self):
        for f in self.tmpfiles:
            os.remove(f)

class CSSSprite(FileFilter):
    """ process @include sprite('/path/to/sprite') """

    rewrite_re = re.compile("@import sprite\(\s*[\"']([a-zA-Z/_\.\-]+?)['\"]?\s*\)\s*;?", re.UNICODE)
    def __init__(self, **kwargs):
        super(CSSSprite, self).__init__(**kwargs)
        assert self.filetype == 'css', (
            'CSSSprite only supports CSS output. '
            'The parent filter expects "%s".' % self.filetype)

    def filter_output(self, content, name, variation):
        return self.rewrite_re.sub(self.make_imports, content)

    def make_imports(self, match):
        fname = match.group(1)
        split_path = os.path.split(fname)
        sprite_file = split_path[-1]
        sprite_name = os.path.join(split_path[:-1])[0].lstrip('/') 
        css = SpriteBuilder(sprite_name.rstrip("/"))
        return css.render_include(sprite_file)
