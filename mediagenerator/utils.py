from . import settings as media_settings
from .settings import (GLOBAL_MEDIA_DIRS, PRODUCTION_MEDIA_URL,
                       IGNORE_APP_MEDIA_DIRS, MEDIA_GENERATORS, DEV_MEDIA_URL,
                       GENERATED_MEDIA_NAMES_MODULE, GENERATED_MEDIA_BLOCKS_MODULE,)


from django.conf import settings
from django.core.cache import get_cache, InvalidCacheBackendError
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.utils.http import urlquote
import os
import re
import threading

try:
    NAMES = import_module(GENERATED_MEDIA_NAMES_MODULE).NAMES
except (ImportError, AttributeError):
    NAMES = None

try:
    _media_blocks = import_module(GENERATED_MEDIA_BLOCKS_MODULE)
    MEDIA_BLOCKS_FILES = _media_blocks.MEDIA_BLOCKS_FILES
    MEDIA_BLOCKS_BUNDLES = _media_blocks.MEDIA_BLOCKS_BUNDLES
    if media_settings.MEDIA_DEV_MODE:
        from mediagenerator.generators.bundles import provider
        provider.default.set_data(MEDIA_BLOCKS_BUNDLES.values())
except (ImportError, AttributeError):
    MEDIA_BLOCKS_FILES = None
    MEDIA_BLOCKS_BUNDLES = None


_backends_cache = {}
_media_dirs_cache = []

_generators_cache = []
_generated_names = {}
_backend_mapping = {}
_refresh_lock = threading.Lock()


def _load_generators():
    if not _generators_cache:
        for name in MEDIA_GENERATORS:
            backend = load_backend(name)()
            _generators_cache.append(backend)
    return _generators_cache


def _refresh_dev_names():
    try:
        _refresh_lock.acquire()
        _generated_names.clear()
        _backend_mapping.clear()
        for backend in _load_generators():
            for key, url, hash in backend.get_dev_output_names():
                versioned_url = urlquote(url)
                if hash:
                    versioned_url += '?version=' + hash
                _generated_names.setdefault(key, [])
                _generated_names[key].append(versioned_url)
                _backend_mapping[url] = backend
    finally:
        _refresh_lock.release()


class _MatchNothing(object):
    def match(self, content):
        return False


def prepare_patterns(patterns, setting_name):
    """Helper function for patter-matching settings."""
    if isinstance(patterns, basestring):
        patterns = (patterns,)
    if not patterns:
        return _MatchNothing()
    # First validate each pattern individually
    for pattern in patterns:
        try:
            re.compile(pattern, re.U)
        except re.error:
            raise ValueError("""Pattern "%s" can't be compiled """
                             "in %s" % (pattern, setting_name))
    # Now return a combined pattern
    return re.compile('^(' + ')$|^('.join(patterns) + ')$', re.U)


def get_production_mapping():
    if NAMES is None:
        raise ImportError('Could not import %s. This '
                          'file is needed for production mode. Please '
                          'run manage.py generatemedia to create it.'
                          % GENERATED_MEDIA_NAMES_MODULE)
    return NAMES


def get_media_mapping():
    if media_settings.MEDIA_DEV_MODE:
        return _generated_names
    return get_production_mapping()


def get_media_url_mapping():
    if media_settings.MEDIA_DEV_MODE:
        base_url = DEV_MEDIA_URL
    else:
        base_url = PRODUCTION_MEDIA_URL

    mapping = {}
    for key, value in get_media_mapping().items():
        if isinstance(value, basestring):
            value = (value,)
        mapping[key] = [base_url + url for url in value]

    return mapping


def media_urls(key, refresh=False):
    if media_settings.MEDIA_DEV_MODE:
        if refresh:
            _refresh_dev_names()
        return [DEV_MEDIA_URL + url for url in _generated_names[key]]
    return [PRODUCTION_MEDIA_URL + get_production_mapping()[key]]


def media_url(key, refresh=False):
    urls = media_urls(key, refresh=refresh)
    if len(urls) == 1:
        return urls[0]
    raise ValueError('media_url() only works with URLs that contain exactly '
                     'one file. Use media_urls() (or {% include_media %} in templates) instead.')


def get_media_dirs():
    if not _media_dirs_cache:
        media_dirs = GLOBAL_MEDIA_DIRS[:]
        for app in settings.INSTALLED_APPS:
            if app in IGNORE_APP_MEDIA_DIRS:
                continue
            for name in (u'static', u'media'):
                app_root = os.path.dirname(import_module(app).__file__)
                media_dirs.append(os.path.join(app_root, name))
        _media_dirs_cache.extend(media_dirs)
    return _media_dirs_cache


def find_file(name, media_dirs=None):
    if media_dirs is None:
        media_dirs = get_media_dirs()
    for root in media_dirs:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            return path


def read_text_file(path):
    fp = open(path, 'r')
    output = fp.read()
    fp.close()
    return output.decode('utf8')


def load_backend(backend):
    if backend not in _backends_cache:
        module_name, func_name = backend.rsplit('.', 1)
        _backends_cache[backend] = _load_backend(backend)
    return _backends_cache[backend]


def _load_backend(path):
    module_name, attr_name = path.rsplit('.', 1)
    try:
        mod = import_module(module_name)
    except (ImportError, ValueError), e:
        raise ImproperlyConfigured(
            'Error importing backend module %s: "%s"' % (module_name, e))
    try:
        return getattr(mod, attr_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" backend' % (module_name, attr_name))


def get_media_bundles_names(block_name):
    if media_settings.MEDIA_DEV_MODE:
        provider = import_module("mediagenerator.generators.bundles.provider")
        bundles = _get_block_bundles(block_name)
        provider.default.set_data(bundles)
        _refresh_dev_names()
        return [b[0] for b in bundles]
    else:
        files, bundles = get_media_bundles_blocks()
        return files[block_name]


def get_media_bundles_blocks():
    if media_settings.MEDIA_DEV_MODE:
        return _get_dev_media_bundles_blocks()
    else:
        return MEDIA_BLOCKS_FILES, MEDIA_BLOCKS_BUNDLES


def _get_dev_media_bundles_blocks(refresh_names=True):
    blocks_files = {}
    blocks_bundles = {}
    for path in settings.TEMPLATE_DIRS:
        os.path.walk(path, _walk_tmpl, (path, blocks_bundles, blocks_files))

    provider = import_module("mediagenerator.generators.bundles.provider")
    provider.default.set_data(blocks_bundles.values())
    if refresh_names:
        _refresh_dev_names()
    return blocks_files, blocks_bundles


def _walk_tmpl(conf, dirname, names):
    tmpl_dir, blocks_bundles, blocks_files = conf
    tmpl_dir += "/"
    for name in names:
        fullname = os.path.join(dirname, name)
        if os.path.isdir(fullname):
            continue

        if not fullname.endswith(".html"):
            continue

        fullname = fullname.replace(tmpl_dir, "")
        bundles = _get_block_bundles(fullname)
        if len(bundles):
            blocks_files[fullname] = [b[0] for b in bundles]
            for b in bundles:
                bname = b[0]
                if bname in blocks_bundles and blocks_bundles[bname] != b:
                    raise Exception(
                        "Different bundles with same name: `%s`" % bname)

                blocks_bundles[bname] = b


def _get_block_bundles(block_name):
    from mediagenerator.generators.bundles.collector import collector
    meta_found, bundles = collector.find_bundles(block_name)
    if meta_found:
        return bundles
    else:
        return []


def atomic_store(path, content):
    tmp = path + '.' + str(os.getpid())
    open(tmp, 'w').write(content)
    os.rename(tmp, path)


try:
    _persistent_cache = get_cache('mediagenerator')

    def cache_get(key):
        return _persistent_cache.get(key)

    def cache_set(key, value):
        print "cache miss for", key
        _persistent_cache.set(key, value, timeout=28*24*3600)

except InvalidCacheBackendError:
    def cache_get(key):
        return None

    def cache_set(key, value):
        pass
