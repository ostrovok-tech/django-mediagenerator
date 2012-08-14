
import jsbeautifier
from mediagenerator.generators.bundles.base import FileFilter

class JSBeautify(FileFilter):
    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(JSTFilter, self).get_dev_output(name, variation)

        return jsbeautifier.beautify(content)
