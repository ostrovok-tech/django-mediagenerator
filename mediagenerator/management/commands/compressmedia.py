from pprint import pprint
from os.path import splitext, dirname, abspath, exists, join
from os import chdir, mkdir, rename, rmdir, getpid
import sys
from shutil import rmtree, copyfile
from subprocess import check_call
import hashlib

from django.core.management.base import NoArgsCommand
from django.utils.importlib import import_module

from ... import settings
from ...api import generate_media, prepare_media

CACHE_DIR = '/tmp/yuibatch/'

def cache_path(src):
    m = hashlib.md5()
    m.update(open(src).read())
    return join(CACHE_DIR, m.hexdigest())


def atomic_cp(src, dst):
    tmp = dst + '.' + str(getpid())
    copyfile(src, tmp)
    rename(tmp, dst)

class Command(NoArgsCommand):
    help = 'Combines and compresses your media files and saves them in _generated_media.'

    requires_model_validation = False

    def handle_noargs(self, **options):
        try:
            NAMES = import_module(settings.GENERATED_MEDIA_NAMES_MODULE).NAMES
        except ImportError:
            print "Nothing to compress, run ./manage.py generatemedia first"
            return

        check_call(['mkdir', '-p', CACHE_DIR])
        

        exts = ('css', 'js')
        groups = dict((ext, []) for ext in exts)
        for k, v in NAMES.items():
            ext = splitext(k)[1][1:]
            if ext in exts:
                groups[ext].append(v)
        
        chdir(settings.GENERATED_MEDIA_DIR)
        if exists('__yui__'):
            rmtree('__yui__')
        mkdir('__yui__')


        for group, files_all in groups.items():
            files4yui = []
            for f in files_all:
                cached_path = cache_path(f)
                if exists(cached_path):
                    atomic_cp(cached_path, f)
                else:
                    files4yui.append((f, cached_path))

            print 'compressing', len(files4yui), group, 'files'
            if files4yui:
                if len(files4yui) == 1:
                    f = files4yui[0][0]
                    check_call(['yui-compressor', '-o', join('__yui__', f), f])
                else:
                    check_call(['yui-compressor', '-o', '^:__yui__/'] + [t[0] for t in files4yui])
                yui = abspath('__yui__')
                for f, cached_path in files4yui:
                    atomic_cp(join(yui, f), cached_path)
                    rename(join(yui, f), f)

        rmdir('__yui__')
