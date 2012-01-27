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
        self.iterkey = -1
        return self

    def __len__(self):
        return len(self.p)

    def __getitem__(self, at):
        return self.p[at]

    def __setitem__(self, at, i):
        self.p[at] = i

    def next(self):
        self.iterkey += 1
        if self.iterkey >= len(self.p):
            raise StopIteration
        else:
            return self.p[self.iterkey]

default = Provider()
