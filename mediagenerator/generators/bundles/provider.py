class Provider(object):
    def __init__(self, default_data=None):
        self.default = default_data
        self.p = []
        
        try:
            from mediagenerator.utils import MEDIA_BLOCKS_BUNDLES
            if MEDIA_BLOCKS_BUNDLES:
                self.p = MEDIA_BLOCKS_BUNDLES.values()
        except (ImportError, AttributeError):
            print "Unable to import MEDIABLOCKS_BUNDLES"


        self.iterkey = -1

    def set_data(self, data):
        if self.default:
            self.p = list(self.default) + data
        else:
            self.p = data

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

default = Provider()
