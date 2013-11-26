"""
Preprocess imports, sprites and urlfix using mediagenerator pipes and then
process scss using ruby-scss.
"""
import hashlib
from subprocess import Popen, PIPE
import zlib

from django.utils.encoding import smart_str
from django.conf import settings

from mediagenerator.generators.bundles.base import FileFilter
from mediagenerator.utils import cache_get, cache_set


class ScssFilter(FileFilter):

    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(ScssFilter, self).get_dev_output(name, variation)

        content = smart_str(content)
        cache_key = "scssz_" + hashlib.md5(content).hexdigest()
        stdout = cache_get(cache_key)
        if stdout is not None:
            return zlib.decompress(stdout)


        scss = getattr(settings, 'MEDIA_SCSS_PATH', 'scss')

        command = [scss, '--stdin', '--style=expanded', '-q']
        pipe = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = pipe.communicate(content)
        if stderr:
            raise RuntimeError(
                "scss (%s) exited with error: %s" % (name, stderr))

        cache_set(cache_key, zlib.compress(stdout, 3))
        return stdout
