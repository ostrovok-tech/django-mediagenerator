import os

from django.core.management.base import NoArgsCommand
from django.utils.importlib import import_module

from mediagenerator import settings


class Command(NoArgsCommand):
    help = 'Removes files from _generated_media not stored in _generated_media_file.pu'

    files_removed = 0


    
    def handle_noargs(self, **options):
        try:
            names = import_module(settings.GENERATED_MEDIA_NAMES_MODULE).NAMES
        except (ImportError, AttributeError):
            print "No found generated media. Exiting."
            return


        namesset = set()
        for n in names.values():
            namesset.add(os.path.relpath(os.path.join(settings.GENERATED_MEDIA_DIR, n)))

        os.path.walk(settings.GENERATED_MEDIA_DIR, self.walk, namesset)
        print "Cleanup done, files removed: %d" % self.files_removed

    def walk(self, current_content, dirname, names):
        relname = os.path.relpath(dirname)
        for fname in names:
            full_name = os.path.join(relname, fname)

            if not os.path.isfile(full_name): continue
            if full_name in current_content: continue
            print "Removing unnecessary file %s" % full_name
            os.remove(full_name)
            self.files_removed += 1
