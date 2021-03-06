import collections


class DataModelError(Exception):
    pass


class VarAccessError(DataModelError):
    pass


class AddressSpace(object):
    pass


class CObj(object):
    """
    All C objects are instances of this class
    """

    def __init__(self, ctype, adr_space):
        self.ctype = ctype
        self.adr_space = adr_space

    @property
    def initialized(self):
        return False

    @property
    def ptr(self):
        return PtrCObj(self.ctype.ptr, self.adr_space, self)


class BoundCType(object):

    def __init__(self, base_ctype, adr_space):
        self.adr_space = adr_space
        self.base_ctype = base_ctype

    def __call__(self, *args, **argv):
        return self.base_ctype(self.adr_space, *args, **argv)

    def __repr__(self):
        return '<bound ' + repr(self.base_ctype)[1:]

    def __getattr__(self, item):
        return getattr(self.base_ctype, item)

    def __eq__(self, other):
        if isinstance(other, CType):
            return self.base_ctype == other
        elif isinstance(other, BoundCType):
            return (self.base_ctype == other.base_ctype  and
                    self.adr_space == other.adr_space)
        else:
            return NotImplemented

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return str(self.base_ctype)

    @property
    def ptr(self):
        return self.base_ctype.ptr.bind(self.adr_space)

    @property
    def ref(self):
        return self.base_ctype.ref.bind(self.adr_space)



class CType(object):

    COBJ_TYPE = None

    def bind(self, adr_space):
        return BoundCType(self, adr_space)

    def __call__(self, adr_space, *args, **kwargs):
        return self.COBJ_TYPE(self, adr_space, *args, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return BoundCType(self, instance.__adr_space__)

    def __repr__(self):
        return "<CType '{}'>".format(self)

    def cast(self, cobj, adr_space=None):
        """
        :type cobj: any
        :type adr_space: AddressSpace
        :rtype: any
        """
        if isinstance(cobj, CObj):
            if adr_space is None:
                adr_space = cobj.adr_space
            if cobj.ctype == self and cobj.adr_space == adr_space:
                return cobj
        else:
            if adr_space is None:
                raise ValueError("adr_space parameter is required, if cobj "
                                 "is not of type '{}'".format(self))
        return self(adr_space, int(cobj))

    def create_zero_cobj(self, adr_space=None):
        raise NotImplementedError()

    def __eq__(self, other):
        if isinstance(other, CType):
            return self.COBJ_TYPE is other.COBJ_TYPE
        else:
            return NotImplemented

    def __ne__(self, other):
        return not self == other

    @property
    def ptr(self):
        return PtrCType(self)


class IntCObj(CObj):

    def __init__(self, ctype, adr_space, init_val=None):
        super(IntCObj, self).__init__(ctype, adr_space)
        self.__val = None
        if init_val is not None:
            self.val = init_val

    @property
    def initialized(self):
        return self.__val is not None

    def get_val(self):
        if self.initialized:
            return self.__val
        else:
            raise VarAccessError('integer is not initialized')

    def set_val(self, new_value):
        ctype = self.ctype

        if isinstance(new_value, IntCObj):
            if not new_value.initialized:
                raise VarAccessError('Value is not initialized')
            py_obj = new_value.__val
        elif isinstance(new_value, (int, long)):
            py_obj = new_value
        elif isinstance(new_value, tuple) and len(new_value) == 1:
            self.val = new_value[0]
            return
        else:
            raise TypeError(
                '{!r} cannot be converted to object of class {!r}'
                .format(new_value, self))

        if ctype.signed:
            py_obj -= ctype.min()
            py_obj &= ((1 << ctype.bits) - 1)
            py_obj += ctype.min()
        else:
            py_obj &= ((1 << ctype.bits) - 1)

        # convert long back to int if possible
        py_obj_as_int = int(py_obj)
        if py_obj_as_int == py_obj:
            py_obj = py_obj_as_int

        self.__val = py_obj

    val = property(get_val, set_val)

    def __repr__(self):
        if self.initialized:
            return '{}({!r})'.format(self.ctype.name, self.__val)
        else:
            return '{}()'.format(self.ctype.name)

    def __cmp__(self, other):
        self_casted, other_casted = self.ctype.implicit_cast(self, other)
        return cmp(self_casted.__val, other_casted.__val)

    def __nonzero__(self):
        return True if self.__val else False

    def __int__(self):
        if self.__val is None:
            raise VarAccessError('variable is not initialized')
        else:
            return self.__val

    def __sub__(self, other):
        self_casted, other_casted = self.ctype.implicit_cast(self, other)
        pyobj = self_casted.__val - other_casted.__val
        return self_casted.ctype(self.adr_space, pyobj)

    def __isub__(self, other):
        self.val = self - other
        return self

    def __rsub__(self, other):
        self_casted, other_casted = self.ctype.implicit_cast(self, other)
        return other_casted - self_casted


class IntCType(CType):

    COBJ_TYPE = IntCObj

    def __init__(self, name, bits, signed):
        super(IntCType, self).__init__()
        self.bits = bits
        self.signed = signed
        self.implicit_cast = None
        self.name = name

    def min(self):
        if self.signed:
            return -(1 << (self.bits - 1))
        else:
            return 0

    def max(self):
        if self.signed:
            return (1 << (self.bits - 1)) - 1
        else:
            return (1 << self.bits) - 1

    @staticmethod
    def create_implicit_caster(int_ctype, uint_ctype, *other_ctypes):
        def implicit_cast(*cobjs, **argv):
            signed = True
            adr_space = argv.pop('adr_space', None)
            for cobj in cobjs:
                if isinstance(cobj, IntCObj):
                    signed &= cobj.ctype.signed
                    if adr_space is None:
                        adr_space = cobj.adr_space
            result_ctype = int_ctype if signed else uint_ctype
            return [result_ctype.cast(cobj, adr_space) for cobj in cobjs]
        return implicit_cast

    def create_zero_cobj(self, adr_space=None):
        return self(adr_space, 0)

    def __eq__(self, other):
        equality = super(IntCType, self).__eq__(other)
        if equality != True:
            return equality
        return self.name == other.name

    def __str__(self):
        return self.name


class StructCObj(CObj, collections.Sequence):

    def __init__(self, ctype, adr_space, *args, **argv):
        super(StructCObj, self).__init__(ctype, adr_space)
        for attr_name, attr_ctype in ctype.fields:
            self.__dict__[attr_name] = attr_ctype(adr_space)
        if len(args) > 0 or len(argv) > 0:
            if len(args) > len(self.ctype.fields):
                raise TypeError(
                    'too much positional initialization values (must be {}, '
                    'but got {})'.format(len(self.ctype.fields), len(args)))
            init_vals = {fname: ftype.create_zero_cobj()
                         for fname, ftype in self.ctype.fields}
            init_vals.update(zip((nm for nm, ctype in ctype.fields), args))
            init_vals.update(argv)
            self.val = init_vals

    def __repr__(self):
        if self.initialized:
            return '{}({})'.format(self.ctype.struct_name, ', '.join(
                nm+'='+repr(getattr(self, nm)
                            if isinstance(getattr(self, nm), StructCObj)
                            else getattr(self, nm).val)
                for nm, ctype in self.ctype.fields))
        else:
            return '{}()'.format(self.ctype.struct_name)

    @property
    def initialized(self):
        return all(getattr(self, fname).initialized
                   for fname, ftype in self.ctype.fields)

    def get_val(self):
        if self.initialized:
            return {fname: getattr(self, fname).val
                    for fname, ftype in self.ctype.fields}
        else:
            raise VarAccessError('struct is not initialized')

    def set_val(self, new_value):
        if isinstance(new_value, StructCObj):
            if new_value.ctype != self.ctype:
                    raise TypeError('expected mapping {!r} but got {!r}'
                                    .format(self.ctype, new_value.ctype))
            for fname, _ in self.ctype.fields:
                getattr(self, fname).val = getattr(new_value, fname)
        elif isinstance(new_value, collections.Mapping):
            if len(new_value) != len(self.ctype.fields):
                raise TypeError('number of entries in dict is not matching '
                                'number of required fields')
            for fname, ftype in self.ctype.fields:
                try:
                    fval = new_value[fname]
                except KeyError:
                    raise TypeError('struct has no field names {!r}'
                                    .format(fname))
                getattr(self, fname).val = fval
        elif isinstance(new_value, collections.Iterable):
            new_value = tuple(new_value)
            if len(new_value) != len(self.ctype.fields):
                raise TypeError('number of entries in tuple is not matching '
                                'number of required fields')
            for (fname, _), fval in zip(self.ctype.fields, new_value):
                getattr(self, fname).val = fval
        else:
            raise TypeError('The expected mapping, sequence or {!r} but got '
                            '{!r}'.format(self.ctype, type(new_value)))

    def __len__(self):
        return len(self.ctype.fields)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return tuple(getattr(self, fname)
                         for fname, ftype in self.ctype.fields[item])
        else:
            field_name, field_type = self.ctype.fields[item]
            return getattr(self, field_name)

    val = property(get_val, set_val)


class StructCType(CType):

    COBJ_TYPE = StructCObj

    def __init__(self, struct_name, fields):
        super(StructCType, self).__init__()
        self.fields = fields
        self.struct_name = struct_name

    def create_zero_cobj(self, adr_space=None):
        init_vals = {fname: ftype.create_zero_cobj(adr_space)
                     for fname, ftype in self.fields}
        return self(adr_space, **init_vals)

    def __str__(self):
        return 'struct ' + self.struct_name

    def __eq__(self, other):
        equality = super(StructCType, self).__eq__(other)
        if equality != True:
            return equality
        return (self.struct_name == other.struct_name  and
                self.fields == other.fields)


class PtrCObj(CObj):

    def __init__(self, ctype, adr_space, init_ref=None):
        super(PtrCObj, self).__init__(ctype, adr_space)
        self.__ref = None
        if init_ref is not None:
            self.ref = init_ref

    @property
    def initialized(self):
        return self.__ref is not None

    def get_ref(self):
        if self.initialized:
            return self.__ref
        else:
            raise VarAccessError('pointer is not initialized')

    def set_ref(self, new_ref):
        if not isinstance(new_ref, CObj):
            raise ValueError('cannot assign non-CObject to {!r}.ref'
                             .format(self))
        elif new_ref.ctype != self.ctype.ref:
            raise ValueError('{!r} has to match {!r}.ref'
                             .format(new_ref.ctype, self.ctype))
        elif new_ref.adr_space != self.adr_space:
            raise ValueError('Addressspace of pointer has to match .ref')
        else:
            self.__ref = new_ref

    ref = property(get_ref, set_ref)


class PtrCType(CType):

    COBJ_TYPE = PtrCObj

    def __init__(self, ref):
        super(PtrCType, self).__init__()
        self.ref = ref

    def __str__(self):
        return str(self.ref) + ' *'

    def __eq__(self, other):
        equality = super(PtrCType, self).__eq__(other)
        if equality != True:
            return equality
        return self.ref == other.ref


class CProgram(object):

    def __init__(self):
        super(CProgram, self).__init__()
        self.__adr_space__ = AddressSpace()
        self.global_vars()

    def global_vars(self):
        return

    def __repr__(self):
        return "<CProgram>"

    unsigned_long = IntCType('unsigned long', bits=32, signed=False)
    long = IntCType('long', bits=32, signed=True)
    unsigned_int = IntCType('unsigned int', bits=32, signed=False)
    int = IntCType('int', bits=32, signed=True)
    unsigned_short = IntCType('unsigned short', bits=16, signed=False)
    short = IntCType('short', bits=16, signed=True)
    unsigned_char = IntCType('unsigned char', bits=8, signed=False)
    char = IntCType('char', bits=8, signed=True)
    
    long.implicit_cast = unsigned_long.implicit_cast = \
    int.implicit_cast = unsigned_int.implicit_cast = \
    short.implicit_cast = unsigned_short.implicit_cast = \
    char.implicit_cast = unsigned_char.implicit_cast = \
        IntCType.create_implicit_caster(int, unsigned_int,
                                        long, unsigned_long,
                                        short, unsigned_short,
                                        char, unsigned_char)
