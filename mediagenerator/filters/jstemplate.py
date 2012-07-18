import os.path
import re

from mediagenerator.utils import find_file
from mediagenerator.generators.bundles.base import FileFilter

class JSTFilter(FileFilter):

    evaluate    = re.compile("<%([\s\S]+?)%>", re.MULTILINE|re.UNICODE|re.IGNORECASE)
    interpolate = re.compile("<%=([\s\S]+?)%>", re.MULTILINE|re.UNICODE|re.IGNORECASE)
    escape      = re.compile("<%-([\s\S]+?)%>", re.MULTILINE|re.UNICODE|re.IGNORECASE)
    include     = re.compile("<%!include (.+?)%>", re.MULTILINE|re.UNICODE|re.IGNORECASE)
    evaluatesub = re.compile("[\r\t\n]", re.MULTILINE)

    def unescape(self, code):
        return code.replace("\\\\", "\\").replace("\\'", "'")

    def compile_tmpl(self, plain, name):
        tmpl     = "MEDIA = window.MEDIA || {};";
        tmpl    += "MEDIA.templates = MEDIA.templates || {};"
        tmpl    += "MEDIA.templates['%s'] = { render: function(obj){" % name
        tmpl    += "var __p=[];"
        tmpl    += "var print=function(){ __p.push.apply(__p,arguments);};"
        tmpl    += "var __esc=function(c){ return window._ && window._.escape ? window._.escape(c) : escape(c) };"
        tmpl    += "with(obj||{}){__p.push('"

        # process includes
        while self.include.search(plain):
            plain = self.include.sub(lambda m: self._read_jst_content(m.group(1)), plain)

        plain = plain.replace("\\", "\\\\")
        plain = plain.replace("'", "\\'")
        plain = self.escape.sub(lambda m: "',__esc(" + self.unescape(m.group(1)) + "),'", plain)
        plain = self.interpolate.sub(lambda m: "', " + self.unescape(m.group(1)) + ",'", plain)
        plain = self.evaluate.sub(lambda m: "');" + self.evaluatesub.sub(" ", self.unescape(m.group(1))) + ";__p.push('", plain)
        
        plain = plain.replace("\n", "\\n")
        plain = plain.replace("\r", "\\r")
        plain = plain.replace("\t", "\\t")

        footer  = "');}return __p.join('');}};";

        
        return tmpl + plain + footer

    def _read_jst_content(self, name):
        name = name.strip(' \n\t')
        fname = find_file(name)
        if not fname:
            raise IOError("File not found: '%s'" % name)

        with open(fname, 'r') as f:
            return f.read()

    def get_dev_output(self, name, variation, content=None):
        if not content:
            content = super(JSTFilter, self).get_dev_output(name, variation)

        return self.compile_tmpl(content, name)

    def get_last_modified(self):
        pool = [self.name]
        last_modified = 0
        while len(pool):
            item = pool.pop(0)
            try:
                content = self._read_jst_content(item)
            except IOError:
                return None

            for include in self.include.findall(content):
                fname = include.strip(' \n\t')
                pool.append(fname)
                fname = find_file(fname)
                if not fname:
                    return None

                lm = os.path.getmtime(fname)
                if lm > last_modified:
                    last_modified = lm
        return last_modified
                

