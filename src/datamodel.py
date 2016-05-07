

class AccessUninitializedVarError(Exception):
    pass


class CObject(object):
    """
    All C objects are instances of this class
    """

    PYTHON_TYPE = None

    def __init__(self, init_val=None):
        self.__val = None
        if init_val is not None:
            self.val = init_val

    def get_val(self):
        if self.__val is None:
            raise AccessUninitializedVarError('variable is not inititialized')
        return self.__val

    def set_val(self, new_val):
        self.__val = self.convert(new_val)

    @property
    def is_initialized(self):
        return self.__val is not None

    def copy(self):
        return type(self)(self.__val)

    @classmethod
    def convert(cls, value):
        if isinstance(value, cls.PYTHON_TYPE):
            return value
        elif isinstance(value, cls):
            return value.val
        else:
            raise TypeError("cannot convert from type '{}' to type '{}'"
                            .format(type(value).__name__, cls.__name__))

    def __set__(self, instance, value):
        self.val = value

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.val)

    def __cmp__(self, value):
        return cmp(self.val, self.convert(value))

    val = property(get_val, set_val)


class CInt(CObject):
    PYTHON_TYPE = int


class CProgram(object):

    def __init__(self):
        for attrname in dir(self):
            attr = getattr(self, attrname)
            if isinstance(attr, CObject):
                self.__dict__[attrname] = attr.copy()
