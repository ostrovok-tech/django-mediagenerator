import os
import re
import time

from mediagenerator.generators.bundles.base import FileFilter
from mediagenerator.utils import find_file

class CssImport(FileFilter):
    
    IMPORT = re.compile(r"@import \s*(?P<d>['\"])(.*?)(?P=d)\s*;", re.M|re.U)
    COMMENT = re.compile(r"/\*.*?\*/")
    LINE_COMMENT = re.compile("//.*?\n")

    def __init__(self, **kwargs):
        super(CssImport, self).__init__(**kwargs)
        assert self.filetype == 'css', (
            'CSSSprite only supports CSS output. '
            'The parent filter expects "%s".' % self.filetype)

        self.scss_files = None
    
    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(CssImport, self).get_dev_output(name, variation)

        while self.IMPORT.search(content):
            content = self.COMMENT.sub("", content)
            content = self.LINE_COMMENT.sub("", content)
            content = self.IMPORT.sub(lambda m: self._read_import(m.group(2)), content)
        
        
        return content

    def _read_import(self, name):
        file_name = find_file(name)
        if not file_name:
            raise IOError("File not found: '%s'" % name)
        
        with open(file_name, 'r') as f:
            return f.read()

    def _collect_scss_files(self):
        files = {}
        pool = [self.name]
        last_modified = 0
        while len(pool):
            item = pool.pop(0)
            try:
                content = self._read_import(item)
            except IOError:
                return None

            for quote, include in self.IMPORT.findall(content):
                fname = include.strip(' \n\t')
                pool.append(fname)
                fname = find_file(fname)
                if not fname:
                    return None

                files[fname] = os.path.getmtime(fname)

        return files

    def get_last_modified(self):
        if not self.scss_files:
            self.scss_files = self._collect_scss_files()
            if not self.scss_files:
                return 0

        for f, modified in self.scss_files.items():
            if os.path.getmtime(f) != modified:
                self.scss_files = self._collect_scss_files()
                if not self.scss_files:
                    return 0

        return max([0] + self.scss_files.values())

