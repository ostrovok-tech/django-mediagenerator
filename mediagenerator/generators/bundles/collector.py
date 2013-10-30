import os
import re
import hashlib
import glob2
import hashlib
import cPickle



from .settings import (MEDIA_RELATIVE_RESOLVE, MEDIA_CSS_LOCATION,
    MEDIA_JS_LOCATION, MEDIA_CSS_EXT, MEDIA_JS_EXT, MEDIA_CACHE_DIR )
from ...settings import  MEDIA_DEV_MODE

from django.conf import settings

#from mediagenerator import settings
from mediagenerator.utils import find_file, get_media_dirs, atomic_store
from mediagenerator.templatetags.media import MetaNode
from django import template


class CommentResolver(object):
    resolve_re = re.compile(r"@require (?P<d>['\"])(.*?)(?P=d)", re.M|re.U)
    _cache = {}

    def __init__(self, lang):
        self.lang = lang
        self.comment_start = False
        self.result = []

    def parse_requirements(self, content, fname):
        # for testing purposes
        if MEDIA_RELATIVE_RESOLVE:
            result = []
            for r in self._resolve(content):
                result += _find_files(os.path.split(fname)[0], r)
        else:
            result = self._resolve(content)
        return result

    def resolve(self, fname):
        if fname in self._cache:
            result, time = self._cache[fname]
            mtime = os.path.getmtime(fname)
            if time == mtime: 
                return result

        with open(fname) as sf:
            content = sf.read()

        result = self.parse_requirements(content, fname)

        time = os.path.getmtime(fname)
        self._cache[fname] = result, time
    
        return result

    def _resolve(self, source):
        return [ m.group(2) for m in self.resolve_re.finditer(source) ]

class MediaBlock(object):
    re_js_req = re.compile('//@require (.*)', re.UNICODE)
    _cache = {}
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

        if not MEDIA_DEV_MODE:
            if name in self._cache:
                return self._cache[name]

        resolver = CommentResolver(lang)
        deps = []
        for dep in resolver.resolve(name):
            dep_file = find_file(dep)
            if not dep_file:
                continue

            deps += self._find_deps(dep_file, lang)
            deps.append(dep)

        if not MEDIA_DEV_MODE:
            self._cache[name] = deps
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
        cache_dir, fname = os.path.split(self.cache_fname)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)

        atomic_store(
            self.cache_fname,
            cPickle.dumps({
                "hash" : self.get_hash(tmpls),
                "result" : result,
                "tmpls": sorted(set(tmpls))
            })
        )

    def resolve_tmpl_file_name(self, tmpl_name):
        for dir in settings.TEMPLATE_DIRS:
            check_file = os.path.join(dir, tmpl_name)
            if os.path.exists(check_file):
                return check_file

        return None
        

    def get_hash(self, tmpls):
        if self.md5:
            return self.md5

        src = "version_3"
        
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
        
    __resources__ = {}

    def __init__(self):
        self.pool = None
        self.blocks = None
        self.meta_found = False
        self.root_name = None


    def find_bundles(self, tmpl_name):
        
        collection = self._find_collection(tmpl_name)
        if not len(collection):
            return False, []

        #blocks = list(reversed(blocks))
        res = []
        uniques = set()
        for b in collection:
            res += MediaBlock(b, uniques).get_bundles()
        
        self.normilize_names(res)

        return True, res

    def _load_resource(self, name):
        if name in self.__resources__:
            return self.__resources__[name]

        res = Resource(name)
        self.__resources__[name] = res
        return res

    def _find_collection(self, tmpl_name):
        resource = self._load_resource(tmpl_name)
        content = resource.get_content()
        pool = [resource]
        parser = TemplateParser()
        resources = [resource]
        media_found = False
        while 1:
            parser.parse(content)
            if not media_found and len(parser.media_meta):
                media_found = True

            if len(parser.extends):
                res = self._load_resource(parser.extends[0])
                resource.add_dep(res)
                if res.is_exists():
                    content = res.get_content()
                    resources.insert(0, res)
                    continue

            break

        #if not media_found:
        #    raise IncompleteCollection("No media found for collection %s" % resource.name)
        if not media_found:
            return []

        collection = []
        for res in resources:
            elem = [res.name]
            collection.append(elem)
            pool = [res]
            skip_extends = True
            while len(pool):
                r = pool.pop(0)
                if not r.is_exists():
                    print "Warning: Resource does not exists: %s. From file: %s" % ( r.name, resource.get_abs_path() )
                    continue

                parser.parse(r.get_content())

                if skip_extends:
                    if len(parser.extends):
                        skip_extends = False
                else:
                    for e in parser.extends:
                        extend_res = self._load_resource(e)
                        if extend_res.name in elem:
                            continue

                        pool.append(extend_res)
                        elem.append(extend_res.name)
                        resource.add_dep(extend_res)

                for i in parser.includes:
                    include_res = self._load_resource(i)
                    if include_res.name in elem:
                        continue

                    pool.append(include_res)
                    elem.append(include_res.name)
                    resource.add_dep(include_res)



        return collection
    
    def _find_blocks(self, tmpl):
        tmpl_name = tmpl
        try:
            tmpl = template.loader.get_template(tmpl)
        except Exception, e:
            print "Warning: Unable to parse template `%s`: %s" % (tmpl, repr(e))
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
    
        
class Resource(object):
    class DoesNotExists(Exception):
        pass

    resource_type = "file"

    def __init__(self, name):
        self.name = name
        self.filters = []
        self.deps    = []

    def is_exists(self):
        #return bool(self.manager.locator.find_root_location(self.name))
        return bool(self.get_root_location())

    def get_content(self):
        loc = self.get_abs_path()
        with open(loc, "r") as sf:
            content = sf.read()

        return content

    def get_root_location(self):
        #root_location = self.manager.locator.find_root_location(self.name)
        #if not root_location:
        #    raise self.DoesNotExistsa
        for path in settings.TEMPLATE_DIRS:
            check = os.path.join(path, self.name)
            if os.path.exists(check):
                return path

        return None

    def get_cache_key(self):
        return self.resource_type + "/" + self.name
         
    def get_abs_path(self):
        if not self.get_root_location():
            raise self.DoesNotExists(self.name)

        return os.path.join(self.get_root_location(), self.name)

    def get_extention(self):
        try:
            return self.name.rsplit(".", 1)[1] 
        except IndexError:
            return ""

    def get_version(self, typ="mod"):
        if typ == "mod":
            return os.path.getmtime(self.get_abs_path())
        else:
            return hashlib.md5(self.get_content()).hexdigest()
    
    def get_filtered_content(self):
        
        is_cached, content = self.get_cached()
        if is_cached:
            return content

        content = self.get_content()
        for f in self.filters:
            content = f.process(self, content)

        self.set_cached(content)
        return content

    def add_dep(self, dep):
        if dep not in self.deps:
            self.deps.append(dep)

    def add_filter(self, filter):
        self.filters.append(filter)

    def get_cached(self):
        return False, None
        key = self.get_cache_key()
        bad_result = False, None
        if not self.manager.cache.exists(key):
            return bad_result

        data = self.manager.cache.get(key)
        good_result = True, data["content"]

        filter_names = [f.name for f in self.filters]
        if data["filters"] != filter_names:
            return bad_result

        if "version" not in data:
            return good_result

        version_mod, version_hash = data["version"]
        if version_mod == self.get_version("mod") or version_hash == self.get_version("hash"):
            if self._check_deps_version(data["deps"]):
                return good_result

        return bad_result

    def _check_deps_version(self, deps):
        new_deps = []
        for rtype, rname, rexists, vmod, vhash in deps:
            res = find_manager(rtype).load_resource(rname)
            if rexists != res.is_exists():
                return False

            if rexists and vmod != res.get_version("mod") and vhash != res.get_version("hash"):
                return False

            new_deps.append(res)

        self.deps = new_deps
        return True

    def set_cached(self, content):
        return
        deps = []
        for r in self.deps:
            if r.is_exists():
                version_mod = r.get_version("mod")
                version_hash = r.get_version("hash")
            else:
                version_mod = None
                version_hash = False
            deps.append((r.resource_type, r.name, r.is_exists(), version_mod, version_hash))

        data = {
            "filters": [f.name for f in self.filters],
            "version": [self.get_version("mod"), self.get_version("hash")],
            "content": content,
            "deps"   : deps
        }
        self.manager.cache.set(self.get_cache_key(), data)

    def __repr__(self):
        return "<%s: '%s'>" % ( self.__class__.__name__, self.name )


class TemplateParser(object):
    
    re_tags = re.compile(r'{%\s*(comment|endcomment|extends|include|media_meta)\s*(.*?)\s*%}')
    re_tmplname = re.compile(r"(?P<d>['\"])(.*?)(?P=d)")

    def parse(self, content):
        self.includes = []
        self.extends = []
        self.media_meta = []
        self.in_comment = False
        self.re_tags.sub(self._parse, content)

    def _parse(self, match):
        if match.group(1) == "comment":
            self.in_comment = True
        elif match.group(1) == "endcomment":
            self.in_comment = False
        elif self.in_comment:
            return
        elif match.group(1) == "extends":
            tmpl_name = self._find_tmpl_name(match.group(2))
            if tmpl_name:
                self.extends.append(tmpl_name)
        elif match.group(1) == "include":
            tmpl_name = self._find_tmpl_name(match.group(2))
            if tmpl_name:
                self.includes.append(tmpl_name)
        elif match.group(1) == "media_meta":
            self.media_meta.append(match.group(2))

    def _find_tmpl_name(self, string):
        if not (string.startswith("'") or string.startswith('"')):
            #print "Unable to determinte template name: dynamic names resolving not supported"
            return None

        match = self.re_tmplname.match(string)
        return match.group(2)

    def parse_includes(self, match):
        self.includes.append(match.group(1))


collector = Collector()
