import os.path
import re
import glob2
import hashlib
import cPickle



from .settings import (MEDIA_RELATIVE_RESOLVE, MEDIA_CSS_LOCATION,
    MEDIA_JS_LOCATION, MEDIA_CSS_EXT, MEDIA_JS_EXT, MEDIA_CACHE_DIR, MEDIA_CACHE_MODE )

from django.conf import settings

#from mediagenerator import settings
from mediagenerator.utils import find_file, get_media_dirs
from mediagenerator.templatetags.media import MetaNode
from django import template

class CommentResolver(object):
    resolve_re = re.compile(r"^ *(/?\*?/?)? *(@require (?P<d>['\"])(.*?)(?P=d))? *(/?\*?/?).*$", re.M|re.U)
    _cache = {}
    def __init__(self, lang):
        self.lang = lang
        self.comment_start = False
        self.result = []

    def resolve(self, fname):
        fname = find_file(fname)
        if fname in self._cache:
            result, time = self._cache[fname]
            mtime = os.path.getmtime(fname)
            if time == mtime: 
                return result

        with open(fname) as sf:
            content = sf.read()
         
        # for testing purposes
        if MEDIA_RELATIVE_RESOLVE:
            result = self._resolve(content)
        else:
            result = []
            for r in self._resolve(content):
                result += _find_files(os.path.split(fname)[0], r)

        time = os.path.getmtime(fname)
        self._cache[fname] = result, time
    
        return result

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

        # make ie bundles here
        ie_res = []
        for bundle in res:
            if bundle[0].endswith(".js"):
                ie_res.append(bundle)
                continue

            name, ext = bundle.pop(0).rsplit(".", 1)

            ie_bundle = [name + ".ie." + ext]
            norm_bundle = [name + "." + ext]
            for entry in bundle:
                if entry.endswith(".ie.css"):
                    ie_bundle.append(entry)
                else:
                    norm_bundle.append(entry)


            if len(norm_bundle) > 1:
                ie_res.append(norm_bundle)
            
            if len(ie_bundle) > 1:
                ie_res.append(ie_bundle)

        return ie_res


    def _find_js(self, name):
        result = []
        for ext in MEDIA_JS_EXT:
            if isinstance(MEDIA_JS_LOCATION, basestring):
                locations = [MEDIA_JS_LOCATION]
            else:
                locations = MEDIA_JS_LOCATION

            for location in locations:
                entry_name = os.path.join(location, name + "." + ext)
                entry_file = find_file(entry_name)
                if entry_file:
                    result += self._find_deps(entry_file, "js")
                    result.append(entry_name)
                    break

        return result
    
    def _find_css(self, name):
        result = []
        for ext in MEDIA_CSS_EXT:
            if isinstance(MEDIA_CSS_LOCATION, basestring):
                locations = [MEDIA_CSS_LOCATION]
            else:
                locations = MEDIA_CSS_LOCATION

            for location in locations:
                entry_name = os.path.join(location, name + "." + ext)
                entry_file = find_file(entry_name)
                if entry_file:
                    result += self._find_deps(entry_file, "css")
                    result.append(entry_name)
                    break

        return result


    def _find_deps(self, name, lang):
        pool = [name]
        deps = []
        resolver = CommentResolver(lang)
        while len(pool):
            current_deps = resolver.resolve(pool.pop(0))
            for dep in reversed(current_deps):
                dep_file = find_file(dep)
                if dep_file and dep not in deps:
                    pool.append(dep_file)
                    deps.insert(0, dep)
        return deps

class TmplFileCache(object):
    location = MEDIA_CACHE_DIR
    def __init__(self, tmpl_name):
        self.tmpl_name = tmpl_name
        self.cache_fname = None
        self.md5 = None

        if not os.path.isdir(self.location):
            os.makedirs(self.location)

    def check_result(self):
        tmpl_name = self.tmpl_name
        cache_fname = self.cache_fname = os.path.join(self.location, tmpl_name)
        
        tmpl_file = self.resolve_tmpl_file_name(tmpl_name)

        if not tmpl_file:
            return None, False

        if not os.path.exists(cache_fname):
            return None, False

        with open(cache_fname, "r") as sf:
            info = cPickle.load(sf)



        if info["hash"] == self.get_hash(info["tmpls"]):
            return info["result"], True
        else:
            return None, False

    def store_result(self, tmpls, result):
        if MEDIA_CACHE_MODE != 'rw':
            return

        cache_dir, fname = os.path.split(self.cache_fname)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)

        with open(self.cache_fname, "w") as sf:
            cPickle.dump({
                "hash" : self.get_hash(tmpls),
                "result" : result,
                "tmpls": sorted(set(tmpls))
            }, sf)

    def resolve_tmpl_file_name(self, tmpl_name):
        for dir in settings.TEMPLATE_DIRS:
            check_file = os.path.join(dir, tmpl_name)
            if os.path.exists(check_file):
                return check_file

        return None
        

    def get_hash(self, tmpls):
        if self.md5:
            return self.md5

        src = "version_2"
        
        for tmpl_name in sorted(set(tmpls)):
            tmpl_file = self.resolve_tmpl_file_name(tmpl_name)
            if not tmpl_file:
                src += "!no_file!"
                continue

            if os.path.exists(tmpl_file):
                with open(tmpl_file, "r") as sf:
                    src += sf.read()

        self.md5 = hashlib.md5(src).digest()
        return self.md5
        
class Collector(object):

    def __init__(self):
        self.pool = None
        self.blocks = None
        self.meta_found = False
        self.root_name = None

    def find_bundles(self, tmpl):
        if self.pool: return []
        if not tmpl: return []

        tmpl_name = tmpl
        cache = TmplFileCache(tmpl_name)
        result, in_cache = cache.check_result()
        if not in_cache:
            meta_found, blocks, tmpls = self._find_blocks(tmpl, cache)
            cache.store_result(tmpls, (meta_found, blocks))
        else:
            meta_found, blocks = result

        res = []
        blocks = list(reversed(blocks))
        uniques = set()
        for b in blocks:
            res += MediaBlock(b, uniques).get_bundles()
        
        self.normilize_names(res)

        return meta_found, res
    
    def _find_blocks(self, tmpl, cache):
        tmpl_name = tmpl
        try:
            tmpl = template.loader.get_template(tmpl)
        except Exception, e:
            print "Warning: Unable to parse template `%s`: %s" % (tmpl, repr(e))
            cache.store_result([tmpl_name], (False, []))
            return False, [], []


    
        self.root_name = tmpl.name
        self.pool = [[tmpl.name]]
        self.blocks = [self.pool[0]]
        self.tmpls = [tmpl_name]
        for node in tmpl.nodelist:
            self.event(node)

        blocks = self.blocks
        meta_found = self.meta_found
        tmpls = self.tmpls
        self.pool = None
        self.blocks = None
        self.root_name = None
        self.meta_found = False
        self.tmpls = None

        return meta_found, blocks, tmpls



    def normilize_names(self, blocks):
        for block in blocks:
            block[0] = block[0].replace("/", "-")



    def event(self, arg):
        if isinstance(arg, template.loader_tags.ExtendsNode):
            if not arg.parent_name:
                raise Exception("Only static extend suported")
            
            try:
                tmpl = template.loader.get_template(arg.parent_name)
                self.tmpls.append(tmpl.name)
                for node in arg.nodelist:
                    self.event(node)
                
                extend = [arg.parent_name]
                self.blocks.append(extend)
                self.pool.append(extend)
                for node in tmpl.nodelist:
                    self.event(node)
                self.pool.pop()

            except template.base.TemplateDoesNotExist, e:
                print "Warning: Block `%s` will not fully processed: %s" % (arg.parent_name, repr(e))
            
        elif isinstance(arg, template.loader_tags.BlockNode):
           for node in arg.nodelist:
               self.event(node)
        elif isinstance(arg, template.loader_tags.IncludeNode):
            print "Warning: Block `%s` will not fully processed: only static include supported" % self.root_name
        elif isinstance(arg, template.loader_tags.ConstantIncludeNode):
            if not arg.template:
                print "Warnign: Block `%s` will not fully processed: not all includes exists" % self.root_name
                return

            self.pool[-1].append(arg.template.name)
            self.tmpls.append(arg.template.name)
            for node in arg.template.nodelist:
                self.event(node)
        elif isinstance(arg, template.defaulttags.IfNode):
            for node in arg.nodelist_true:
                self.event(node)
            for node in arg.nodelist_false:
                self.event(node)
        elif isinstance(arg, template.defaulttags.ForNode):
            for node in arg:
                self.event(node)
        elif isinstance(arg, template.defaulttags.WithNode):
            for node in arg.nodelist:
                self.event(node)
        elif isinstance(arg, MetaNode):
            self.meta_found = True

def _find_files(path_from, pattern):
    
    path_root = os.path.abspath(".")

    if pattern.startswith("."):
        search_prefix = path_from.replace(path_root, "").strip("/")
        pattern = search_prefix + "/" + pattern
    
    found = []
    for cdir in get_media_dirs():
        if not os.path.isdir(cdir):
            continue

        os.chdir(cdir)
        found = glob2.glob(pattern)
        if found:
            break

    return [os.path.normpath(f) for f in found]
    
        


collector = Collector()
