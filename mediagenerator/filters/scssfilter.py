
from scss import Scss

from mediagenerator.generators.bundles.base import FileFilter


class ScssFilter(FileFilter):
    
    def __init__(self, **kwargs):
        super(ScssFilter, self).__init__(**kwargs)
        assert self.filetype == 'css', (
            'ScssFilter only supports CSS output. '
            'The parent filter expects "%s".' % self.filetype)
    
    def get_dev_output(self, name, variation, content=None):
        compiler = Scss()
        
        # here we support piped output
        if not content:
            content = super(ScssFilter, self).get_dev_output(name, variation)
        
        return compiler.compile(str(content.encode("utf8")))


        

    
