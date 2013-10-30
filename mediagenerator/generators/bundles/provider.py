from .settings import MEDIA_BUNDLES
class Provider(object):
    def __init__(self, default_data=None):
        self.default = default_data
        self.p = {}
        self.iterkey = -1

    def set_data(self, data):
        self.p = {}
        self.update(data)

    def update(self, bundles):
        for bundle in bundles:
            self.p[bundle[0]] = bundle
            bundle_name = bundle[0]

    def __iter__(self):
        for b in self.default:
            yield b

        for b in self.p.values():
            yield b

    def __len__(self):
        return len(self.default) + len(self.p)


default = Provider(MEDIA_BUNDLES)
