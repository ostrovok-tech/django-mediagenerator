from django.conf import settings

DEFAULT_MEDIA_FILTERS = getattr(settings, 'DEFAULT_MEDIA_FILTERS', {
    'ccss': 'mediagenerator.filters.clever.CleverCSS',
    'coffee': 'mediagenerator.filters.coffeescript.CoffeeScript',
    'css': (
        'mediagenerator.filters.urlfix.UrlFixFilter',
        'mediagenerator.filters.sprite.CSSSprite',
    ),
    'html': 'mediagenerator.filters.template.Template',
    'py': 'mediagenerator.filters.pyjs_filter.Pyjs',
    'pyva': 'mediagenerator.filters.pyvascript_filter.PyvaScript',
    'sass': 'mediagenerator.filters.sass.Sass',
    'scss': (
        'mediagenerator.filters.cssimport.CssImport',
        'mediagenerator.filters.urlfix.UrlFixFilter',
        'mediagenerator.filters.sprite.CSSSprite',
        'mediagenerator.filters.scssfilter.ScssFilter',
    ),
    'less': 'mediagenerator.filters.less.Less',
    'sprite': 'mediagenerator.filters.sprite.Sprite',
    'jst': 'mediagenerator.filters.jstemplate.JSTFilter',
    'js': 'mediagenerator.filters.urlfix.UrlFixFilter'
})


ROOT_MEDIA_FILTERS = getattr(settings, 'ROOT_MEDIA_FILTERS', {})

# These are applied in addition to ROOT_MEDIA_FILTERS.
# The separation is done because we don't want users to
# always specify the default filters when they merely want
# to configure YUICompressor or Closure.
BASE_ROOT_MEDIA_FILTERS = getattr(settings, 'BASE_ROOT_MEDIA_FILTERS', {
    '*': 'mediagenerator.filters.concat.Concat',
    #'css': 'mediagenerator.filters.cssurl.CSSURL',
})

MEDIA_BUNDLES = getattr(settings, 'MEDIA_BUNDLES', [])
TEMPLATE_DIRS = getattr(settings, 'TEMPLATE_DIRS', ())
MEDIA_CSS_LOCATION = getattr(settings, "MEDIA_CSS_LOCATION", "css")
MEDIA_JS_LOCATION = getattr(settings, "MEDIA_JS_LOCATION", "js")
MEDIA_CSS_EXT = getattr(settings, "MEDIA_CSS_EXT", ('ie.css', 'css', 'scss'))
MEDIA_JS_EXT = getattr(settings, "MEDIA_JS_EXT", ('js', 'jst'))
MEDIA_RELATIVE_RESOLVE = getattr(settings, "MEDIA_RELATIVE_RESOLVE", False)
MEDIA_CACHE_DIR = getattr(settings, 'MEDIA_CACHE_DIR', '/var/cache/django-mediacache')
