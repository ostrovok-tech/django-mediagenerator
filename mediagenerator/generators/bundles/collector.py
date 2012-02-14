import os.path
import re
import hashlib


from .settings import (MEDIA_CSS_LOCATION,
    MEDIA_JS_LOCATION, MEDIA_CSS_EXT, MEDIA_JS_EXT )

#from mediagenerator import settings
from mediagenerator.utils import find_file
from mediagenerator.templatetags.media import MetaNode
from django import template

class CommentResolver(object):
    resolve_re = re.compile(r"^ *(/?\*?/?)? *(@require (?P<d>['\"])(.*?)(?P=d))? *(/?\*?/?)$", re.M|re.U)
    _cache = {}
    def __init__(self, lang):
        self.lang = lang
        self.comment_start = False
        self.result = []

    def resolve(self, fname):
        fname = find_file(fname)
        if fname in self._cache:
            result, times = self._cache[fname]
            if not self.is_changed(result, times):
                return result

        with open(fname) as sf:
            content = sf.read()

        result = self._resolve(content)
        times = self.calc_changed(result)
        self._cache[fname] = result, times

        return result

    def calc_changed(self, fnames):
        changed = []
        for f in fnames:
            changed.append(os.path.getmtime(find_file(f)))
        return changed

    def is_changed(self, fnames, times):
        return times != self.calc_changed(fnames)


    def _resolve(self, source):
        self.comment_start = False
        self.result = []
        self.resolve_re.sub(self._filter, source)
        return self.result

    def _filter(self, m):
        if m.group(1) == "/*":
            self.comment_start = True
        
        if self.lang == "js":
            single_comment = m.group(1) == "//"
        else:
            single_comment = False

        if (self.comment_start or single_comment) and m.group(4):
            self.result.append(m.group(4))

        if m.group(1) == "*/" or m.group(5) == "*/":
            self.comment_start = False

        return m.group(0)


class MediaBlock(object):
    re_js_req = re.compile('//@require (.*)', re.UNICODE)
    def __init__(self, block, uniques):
        self.bundle_entries = [re.sub('\.html', "", b) for b in block]
        self.uniques = uniques

    def tmpl_name(self):
        if not len(self.bundle_entries):
            return None
        else:
            return self.bundle_entries[0] + ".html"

    def get_bundles(self):
        res = []
        entries = self.uniques
        for typ in ('js', 'css'):
            bundle_name = self.bundle_entries[0] + "." + typ
            bundle = [bundle_name]
            for name in self.bundle_entries:
                for found in getattr(self, "_find_%s" % typ)(name):
                    if found not in entries:
                        bundle.append(found)
                    entries.add(found)
                    
            if len(bundle) == 1: continue
            res.append(bundle)

        return res


    def _find_js(self, name):
        result = []
        for ext in MEDIA_JS_EXT:
            entry_name = os.path.join(MEDIA_JS_LOCATION, name + "." + ext)
            entry_file = find_file(entry_name)
            if entry_file:
                result += self._find_deps(entry_file, "js")
                result.append(entry_name)

        return result
    
    def _find_css(self, name):
        result = []
        for ext in MEDIA_CSS_EXT:
            entry_name = os.path.join(MEDIA_CSS_LOCATION, name + "." + ext)
            entry_file = find_file(entry_name)
            if entry_file:
                result += self._find_deps(entry_file, "css")
                result.append(entry_name)

        return result


    def _find_deps(self, name, lang):
        pool = [name]
        deps = []
        resolver = CommentResolver(lang)
        while len(pool):

            current_deps = resolver.resolve(pool.pop(0))
            for dep in current_deps:
                dep_file = find_file(dep)
                if dep_file and dep not in deps:
                    pool.append(dep_file)
                    deps.append(dep)
        return deps


class Collector(object):

    def __init__(self):
        self.pool = None
        self.blocks = None
        self.meta_found = False
        self.root_name = None

    def find_bundles(self, tmpl):
        if self.pool: return []
    
        self.root_name = tmpl.name
        self.pool = [[tmpl.name]]
        self.blocks = [self.pool[0]]
        for node in tmpl.nodelist:
            self.event(node)

        blocks = self.blocks
        meta_found = self.meta_found
        self.pool = None
        self.blocks = None
        self.root_name = None
        self.meta_found = False


        res = []
        blocks = list(reversed(blocks))
        uniques = set()
        for b in blocks:
            res += MediaBlock(b, uniques).get_bundles()
        
        self.normilize_names(res)

        return meta_found, res

    def normilize_names(self, blocks):
        for block in blocks:
            # first 6 letters is enought from sha1
            key = hashlib.sha1(''.join(block)).hexdigest()[:6]
            bname, bext = block[0].rsplit(".", 1)
            bname = bname.replace("/", "-")
            if bext:
                block[0] = "%s-%s.%s" % (bname, key, bext)
            else:
                block[0] = "%s-%s" ( bname, key)



    def event(self, arg):
        if isinstance(arg, template.loader_tags.ExtendsNode):
            if not arg.parent_name:
                raise Exception("Only static extend suported")
            
            for node in arg.nodelist:
                self.event(node)
            
            extend = [arg.parent_name]
            self.blocks.append(extend)
            self.pool.append(extend)
            tmpl = template.loader.get_template(arg.parent_name)
            for node in tmpl.nodelist:
                self.event(node)
            self.pool.pop()
            
            
        elif isinstance(arg, template.loader_tags.BlockNode):
           for node in arg.nodelist:
               self.event(node)
        elif isinstance(arg, template.loader_tags.IncludeNode):
            print "Warning: Block `%s` will not fully processed: only static include supported" % self.root_name
        elif isinstance(arg, template.loader_tags.ConstantIncludeNode):
            self.pool[-1].append(arg.template.name)
            for node in arg.template.nodelist:
                self.event(node)
        elif isinstance(arg, template.defaulttags.IfNode):
            for node in arg.nodelist_true:
                self.event(node)
            for node in arg.nodelist_false:
                self.event(node)
        elif isinstance(arg, MetaNode):
            self.meta_found = True

collector = Collector()
