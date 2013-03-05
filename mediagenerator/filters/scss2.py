"""
Preprocess imports, sprites and urlfix using mediagenerator pipes and then
process scss using ruby-scss.
"""
from subprocess import Popen, PIPE

from django.utils.encoding import smart_str
from django.conf import settings

from mediagenerator.generators.bundles.base import FileFilter


class ScssFilter(FileFilter):

    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(ScssFilter, self).get_dev_output(name, variation)

        scss = getattr(settings, 'MEDIA_SCSS_PATH', 'scss')

        command = [scss, '--stdin', '--style=expanded', '-q']
        pipe = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = pipe.communicate(smart_str(content))
        if stderr:
            raise RuntimeError(
                "scss (%s) exited with error: %s" % (name, stderr))

        return stdout
