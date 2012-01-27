def patch():
    from django.conf import settings
    if getattr(settings, "MEDIA_BLOCKS", False):
        from django import template 
        print "Patching"
        from django.views.generic import simple

        orig_render_to_string       = template.loader.render_to_string
        orig_direct_to_template     = simple.direct_to_template

        def render_to_string(template_name, dictionary=None, context_instance=None):
            if dictionary:
                d = dictionary.copy()
            else:
                d = {}

            d["__tmplname__"] = template_name
            return orig_render_to_string(d, context_instance)

        def direct_to_template(request, template, extra_context=None, mimetype=None, **kwargs):
            if extra_context == None:
                d = {}
            else:
                d = extra_context.copy()
            
            d["__tmplname__"] = template
            return orig_direct_to_template(request, template, d, mimetype=None, **kwargs)

        template.loader.render_to_string = render_to_string
        simple.direct_to_template = direct_to_template



