import os.path
import re

from .settings import (MEDIA_CSS_LOCATION,
    MEDIA_JS_LOCATION, MEDIA_CSS_EXT, MEDIA_JS_EXT )

#from mediagenerator import settings
from mediagenerator.utils import find_file
from mediagenerator.templatetags.media import MetaNode
from django import template

class MediaBlock(object):
    re_js_req = re.compile('//@require (.*)', re.UNICODE)
    def __init__(self, block):
        self.bundle_entries = [re.sub('\.html', "", b) for b in block]

    def tmpl_name(self):
        if not len(self.bundle_entries):
            return None
        else:
            return self.bundle_entries[0] + ".html"

    def get_bundles(self):
        res = []
        entries = set()
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
                result += self._find_js_deps(entry_file)
                result.append(entry_name)

        return result


    def _find_js_deps(self, name):
        pool = [name]
        deps = []
        while len(pool):
            with open(pool.pop(0)) as sf:
                content = sf.read()

            current_deps = []
            self.re_js_req.sub(lambda n: current_deps.append(n.group(1)), content)
            for dep in current_deps:
                dep_file = find_file(dep)
                if dep_file and dep not in deps:
                    pool.append(dep_file)
                    deps.append(dep)
        return deps

    def _find_css(self, name):
        result = []
        for ext in MEDIA_CSS_EXT:
            entry_name = os.path.join(MEDIA_CSS_LOCATION, name + "." + ext)
            if find_file(entry_name):
                result.append(entry_name)

        return result

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
        for b in blocks:
            res += MediaBlock(b).get_bundles()

        return meta_found, res

    def event(self, arg):
        print "Event", arg
        if isinstance(arg, template.loader_tags.ExtendsNode):
            if not arg.parent_name:
                raise Exception("Only static extend suported")

            for node in arg.nodelist:
                self.event(node)
            
            extend = [arg.parent_name]
            self.blocks.append(extend)
            self.pool.append(extend)
            tmpl, origin = template.loader.find_template(arg.parent_name)
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
