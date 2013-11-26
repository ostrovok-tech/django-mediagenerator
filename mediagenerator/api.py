from . import settings, utils
from .settings import (GENERATED_MEDIA_DIR, GENERATED_MEDIA_NAMES_FILE,
                       GENERATED_MEDIA_BLOCKS_FILE, MEDIA_GENERATORS) 

from .utils import load_backend, _get_dev_media_bundles_blocks
from django.utils.http import urlquote
import os

def generate_media():

    
    was_dev_mode = settings.MEDIA_DEV_MODE
    settings.MEDIA_DEV_MODE = False

    utils.NAMES = {}

    for backend_name in MEDIA_GENERATORS:
        backend = load_backend(backend_name)()
        for key, url, content in backend.get_output():
            version = backend.generate_version(key, url, content)
            if version:
                base, ext = os.path.splitext(url)
                url = '%s-%s%s' % (base, version, ext)

            path = os.path.join(GENERATED_MEDIA_DIR, url)
            parent = os.path.dirname(path)
            if not os.path.exists(parent):
                os.makedirs(parent)


            fp = open(path, 'wb')
            if isinstance(content, unicode):
                content = content.encode('utf8')
            fp.write(content)
            fp.close()

            utils.NAMES[key] = urlquote(url)

    settings.MEDIA_DEV_MODE = was_dev_mode

    # Generate a module with media file name mappings
    fp = open(GENERATED_MEDIA_NAMES_FILE, 'w')
    fp.write('NAMES = %r' % utils.NAMES)
    fp.close()


def prepare_media():
    if settings.MEDIA_BLOCKS:
        blocks_files, blocks_bundles = _get_dev_media_bundles_blocks(refresh_names=False)
        with open(GENERATED_MEDIA_BLOCKS_FILE, "w") as sf:
            sf.write("MEDIA_BLOCKS_FILES=" + repr(blocks_files) + "\n")
            sf.write("MEDIA_BLOCKS_BUNDLES=" + repr(blocks_bundles) + "\n")

def analyze_media():
    entry_points = set(settings.MEDIA_TESTED_POINTS)
    blocks_files, blocks_bundles = _get_dev_media_bundles_blocks(refresh_names=False)
    for entry in blocks_files.keys():
        if not (entry in entry_points):
            print "Warning: Block `%s` looks like entry point, but is not tested." % entry

    for entry in entry_points:
        if entry not in blocks_files:
            print "Warning: Block `%s` marked as tested, but but is not actuially entry point" % entry
