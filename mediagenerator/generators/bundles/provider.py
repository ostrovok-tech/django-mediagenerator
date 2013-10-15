from .settings import MEDIA_BUNDLES
class Provider(object):
    def __init__(self, default_data=None):
        self.default = default_data
        self.p = []
        self.iterkey = -1

    def set_data(self, data):
        self.p = data

    def update(self, bundles):
        for bundle in bundles:
            bundle_name = bundle[0]
            for existed_bundle in self.p:
                if existed_bundle[0] == bundle_name:
                    break
            else:
                self.p.append(bundle)

    def __iter__(self):
        for b in self.default:
            yield b

        for b in self.p:
            yield b

    def __len__(self):
        return len(self.default) + len(self.p)

    def __getitem__(self, at):
        if at > len(self.default):
            return self.p[at-len(self.default)]
        else:
            return self.default[at]

    def __setitem__(self, at, i):
        if at > len(self.default):
            self.p[at-len(self.default)] = i
        else:
            self.default[at] = i

default = Provider(MEDIA_BUNDLES)
