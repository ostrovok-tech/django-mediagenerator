"""
Preprocess imports, sprites and urlfix using mediagenerator pipes and then
process scss using ruby-scss.
"""
from subprocess import Popen, PIPE
from StringIO import StringIO


from mediagenerator.utils import find_file
from mediagenerator.generators.bundles.base import FileFilter
class ScssFilter(FileFilter):
    
    def get_dev_output(self, name, variation, content=None):

        if not content:
            content = super(ScssFilter, self).get_dev_output(name, variation)

        command = ['/home/jjay/proj/sass/bin/scss', '--stdin', '--style=expanded', '-q']
        pipe = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = pipe.communicate(content)
        if stderr:
            raise RuntimeError("scss (%s) exited with error: %s" % (name, stderr))

        return stdout
