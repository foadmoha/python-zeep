from zeep.utils import process_signature
from zeep.xsd.elements import GroupElement, ListElement, RefElement


class Type(object):

    def accept(self, value):
        raise NotImplementedError

    def parse_xmlelement(self, xmlelement):
        raise NotImplementedError

    def parsexml(self, xml):
        raise NotImplementedError

    def render(self, parent, value):
        raise NotImplementedError

    def resolve(self, schema):
        raise NotImplementedError

    @classmethod
    def signature(cls):
        return ''


class UnresolvedType(Type):
    def __init__(self, qname):
        self.qname = qname

    def resolve(self, schema):
        return schema.get_type(self.qname)


class SimpleType(Type):

    def render(self, parent, value):
        parent.text = self.xmlvalue(value)

    def parse_xmlelement(self, xmlelement):
        return self.pythonvalue(xmlelement.text)

    def xmlvalue(self, value):
        raise NotImplementedError

    def pythonvalue(self, xmlvalue):
        raise NotImplementedError

    def resolve(self, schema):
        return self

    def __call__(self, *args, **kwargs):
        if args:
            return unicode(args[0])
        return u''

    def __str__(self):
        return self.name

    def __unicode__(self):
        return unicode(self.name)


class ComplexType(Type):

    def __init__(self, elements=None, attributes=None):
        self._elements = elements or []
        self._attributes = attributes or []

    def properties(self):
        return list(self._elements) + list(self._attributes)

    def render(self, parent, value):
        for element in self.properties():
            sub_value = getattr(value, element.name)
            element.render(parent, sub_value)

    def __call__(self, *args, **kwargs):
        if not hasattr(self, '_value_class'):
            self._value_class = type(
                self.__class__.__name__ + 'Object', (CompoundValue,),
                {'type': self, '__module__': 'zeep.objects'})

        return self._value_class(*args, **kwargs)

    def resolve(self, schema):
        elements = []
        for elm in self._elements:
            if isinstance(elm, RefElement):
                elm = elm._elm

            if isinstance(elm, GroupElement):
                elements.extend(list(elm))
            else:
                elements.append(elm)
        self._elements = elements
        return self

    def signature(self):
        return ', '.join([
            '%s %s' % (prop.type.name, prop.name) for prop in self.properties()
        ])

    def parse_xmlelement(self, xmlelement):
        instance = self()
        fields = self.properties()
        if not fields:
            return instance

        elements = xmlelement.getchildren()
        fields = iter(fields)
        field = next(fields)
        for element in elements:
            if field.qname != element.tag:
                field = next(fields, None)

            if not field:
                break

            if field.qname != element.tag:
                # XXX Element might be optional
                raise ValueError("Unexpected element: %r" % element.tag)

            result = field.parse(element)
            if isinstance(field, ListElement):
                getattr(instance, field.name).append(result)
            else:
                setattr(instance, field.name, result)

        return instance

    @property
    def name(self):
        return self.__class__.__name__

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.signature())


class CompoundValue(object):

    def __init__(self, *args, **kwargs):
        properties = {
            prop.name: prop() for prop in self.type.properties()
        }
        property_names = [prop.name for prop in self.type.properties()]

        # Set default values
        for key, value in properties.iteritems():
            setattr(self, key, value)

        items = process_signature(property_names, args, kwargs)
        for key, value in items.iteritems():
            setattr(self, key, value)