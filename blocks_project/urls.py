from django.conf.urls.defaults import patterns, url


to_tmpl = 'django.views.generic.simple.direct_to_template'
menu = [
    ("home", "/"),
    ("inherit", "/inherit/"),
    ("double-inherit", "/inherit2/"),
    ("with MEDIA_BUNDLES", "/bundles/"),
    ("conditions", "/cond/"),
]
urlpatterns = patterns('',
    url(r'^$', to_tmpl, {'template' : 'index.html', "extra_context" : { "menu" : menu }}),
    url(r'^inherit/$', to_tmpl, {'template' : 'inherit.html', "extra_context" : { "menu" : menu }}),
    url(r'^inherit2/$', to_tmpl, {'template' : 'inherit2.html', "extra_context" : { "menu" : menu }}),
    url(r'^bundles/$', to_tmpl, {'template' : 'bundles.html', "extra_context" : { "menu" : menu }}),
    url(r'^cond/$', to_tmpl, {'template' : 'cond.html', "extra_context" : { "menu" : menu }}),
)
