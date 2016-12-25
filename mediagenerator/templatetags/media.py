from django import template
from mediagenerator.generators.bundles.utils import _render_include_media
from mediagenerator import utils

register = template.Library()

class MediaNode(template.Node):
    def __init__(self, bundle, variation):
        self.bundle = bundle
        self.variation = variation

    def render(self, context):
        bundle = template.Variable(self.bundle).resolve(context)
        variation = {}
        for key, value in self.variation.items():
            variation[key] = template.Variable(value).resolve(context)

        return _render_include_media(bundle, variation)

@register.tag
def include_media(parser, token):
    try:
        contents = token.split_contents()
        bundle = contents[1]
        variation_spec = contents[2:]
        variation = {}
        for item in variation_spec:
            key, value = item.split('=')
            variation[key] = value
    except (ValueError, AssertionError, IndexError):
        raise template.TemplateSyntaxError(
            '%r could not parse the arguments: the first argument must be the '
            'the name of a bundle in the MEDIA_BUNDLES setting, and the '
            'following arguments specify the media variation (if you have '
            'any) and must be of the form key="value"' % contents[0])

    return MediaNode(bundle, variation)

class MetaNode(template.Node):
    def __init__(self, custom_meta):
        super(MetaNode, self).__init__()
        self.custom_meta = custom_meta

    def render(self, context):
        if "__tmplname__" not in context:
            raise Exception("You can't use tag {% media_meta %} with `MEDIA_BLOCKS` option seted to False")
        if isinstance(context["__tmplname__"], list):
             block_name = context["__tmplname__"][0]
        else:
             block_name = context["__tmplname__"]
        names = utils.get_media_bundles_names(block_name)
        if self.custom_meta:
            names = filter(lambda n: n.endswith("." + self.custom_meta), names)

        if not len(names):
            return "<!-- WARNING: No bundles found for template %s -->" % context["__tmplname__"]
        return "\n".join([_render_include_media(name, {}) for name in names])

@register.simple_tag
def media_url(url):
    return utils.media_url(url)

@register.filter
def media_urls(url):
    return utils.media_urls(url)

@register.tag
def media_meta(parser, token):
    custom_meta = False
    args = token.split_contents()
    if len(args) == 2:
        custom_meta = args[1]
        if custom_meta not in ('css', 'js'):
            raise RuntimeError("Bad context for media_meta: shoud be 'css', 'js' or empty")

    meta = MetaNode(custom_meta)
    return meta
