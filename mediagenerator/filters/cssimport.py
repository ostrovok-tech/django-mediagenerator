import os
import re

from mediagenerator.generators.bundles.base import FileFilter
from mediagenerator.utils import find_file

class CssImport(FileFilter):
    
    rewrite_re = re.compile("@import url\(\s*[\"']([0-9a-zA-Z/_\.\-]+?)['\"]?\s*\)\s*;?", re.UNICODE)
    def __init__(self, **kwargs):
        super(CssImport, self).__init__(**kwargs)
        assert self.filetype == 'css', (
            'CSSSprite only supports CSS output. '
            'The parent filter expects "%s".' % self.filetype)
    
    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(CssImport, self).get_dev_output(name, variation)

        return self.rewrite_re.sub(self.make_imports, content)

    def make_imports(self, match):
        fname = find_file(match.group(1))
        if not fname:
            lineno = match.string.count('\n', 0, match.start())
            print "[%s:%d] Can't find file `%s`" % (self.name, lineno, match.group(1))
            return ""

        try:
            with open(fname, 'r') as sf: content = sf.read()
        except IOError, e:
            lineno = match.string.count('\n', 0, match.start())
            info = self.name, lineno, fname, e
            print "[%s:%d] Can't import file `%s`: %s" % info
            return ""

        return content

    def get_last_modified(self):
        content = super(CssImport, self).get_dev_output(self.name, {})
        files = []
        self.rewrite_re.sub(lambda m: files.append(m.group(1)), content)
        lm = 0
        for f in files:
            fname = find_file(f)
            if not fname: continue
            fmod = os.path.getmtime(fname)
            if fmod > lm: lm = fmod

        return lm
        
    

