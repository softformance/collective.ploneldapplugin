import types

from zope.interface import implements
from zope.component import queryAdapter

from Products.PloneLDAP.property import LDAPPropertySheet

from collective.ploneldapplugin.interfaces import ILDAPAttributeConverter

class DefaultLDAPAttributeConverter(object):
    """This default converter replicates PloneLDAP user property plugin
    behaviour
    """
    
    implements(ILDAPAttributeConverter)
    
    default = ""
    
    def __init__(self, attribute):
        """Default implementation for LDAP attribute values converter
        
        Arguments:
          attribute - python ldap attribute holding ldap related info,
        """
        self.attribute = attribute
    
    def fromLDAPValue(self, value, info):
        """info - tuple containing zope related vars:
        (ldap name, zope name, type (lines|string))
        """
        return value
    
    def toLDAPValue(self, value, info):
        """info - tuple containing zope related vars:
        (ldap name, zope name, type (lines|string))
        """
        return value.strip()

class EnhancedLDAPPropertySheet(LDAPPropertySheet):
    
    def fetchLdapProperties(self, user):
        acl = self._getLDAPUserFolder(user)
        ldap_user = acl.getUserById(user.getId())
        properties = {}

        # Do not pretend to have any properties if the user is not in LDAP
        if ldap_user is None:
            raise KeyError, "User not in LDAP"

        # converters cache
        converters = {}
        attrs = self.getLDAPMultiPlugin(user).getLDAPAttrs()
        for info in self._ldapschema:
            # trying to convert ldap attribute values to python
            # data types properly
            ldapname, zopename, type = info
            attr, name = attrs.get(info, (None, None))
            converter = converters.get(name)
            if converter is None:
                converters[name] = converter = self._getConverter(attr, name)
            
            # convert ldap attribute value or set a default value
            # if there is no value provided for this user yet
            if ldap_user._properties.get(ldapname, None) is not None:
                properties[zopename] = self._fromLDAPValue(converter,
                    ldap_user._properties[ldapname], info)
            else:
                if type == 'lines':
                    properties[zopename] = []
                else:
                    properties[zopename] = None #converter.default

        return properties

    # def hasProperty(self, name):
    #     value = self._properties.get(name, None)
    #     if value is None:
    #         return False
    #     return LDAPPropertySheet.hasProperty(self, name)

    def getProperty(self, name, default=None):
        value = self._properties.get(name, None)
        if value is None:
            value = default
        return value

    def setProperties(self, user, mapping):
        acl = self._getLDAPUserFolder(user)
        ldap_user = acl.getUserById(user.getId())

        # converters cache
        converters = {}
        changes = {}
        schema = dict([(x[1], (x[0], x[2])) for x in self._ldapschema])
        attrs = self.getLDAPMultiPlugin(user).getLDAPAttrs()
        
        for (key, value) in mapping.items():
            # if key in schema and self._properties[key]!=value:
            if key in schema:
                # get ldap attribute converter
                ldapname, zopename, type = info = (schema[key][0], key,
                    schema[key][1])
                attr, name = attrs.get(info, (None, None))
                converter = converters.get(name)
                if converter is None:
                    converters[name] = converter = self._getConverter(attr,
                        name)
                
                # set value if it's different from the previous one
                if self._properties[key] != value:
                    self._properties[key] = value
                    # if value is None we set it to empty string in ldap
                    # this shouldn't be converted by converters, converters
                    # do conversation but not value validation
                    if value is None:
                        value = ""
                    else:
                        value = self._toLDAPValue(converter, value, info)
                    if type == "lines":
                        changes[ldapname] = value
                    else:
                        changes[ldapname] = [value]
        
        acl._delegate.modify(ldap_user.dn, attrs=changes)
        acl._expireUser(user.getUserName())
        self._invalidateCache(user)

    def _getConverter(self, attr, name):
        converter = None
        if attr is not None:
            # check for named adapter
            if name:
                converter = queryAdapter(attr, ILDAPAttributeConverter,
                    name=name)
            # if not found, fallback to default converter
            if converter is None:
                converter = queryAdapter(attr, ILDAPAttributeConverter,
                    name=u"")
        
        # if still no luck, get our own converter
        if converter is None:
            converter = DefaultLDAPAttributeConverter(attr)
        
        return converter
    
    def _fromLDAPValue(self, converter, value, info):
        # handle separately multivalued attributes
        if isinstance(value, (types.ListType, types.TupleType)):
            result = []
            for elem in value:
                result.append(converter.fromLDAPValue(elem, info))
            return result
        else:
            return converter.fromLDAPValue(value, info)

    def _toLDAPValue(self, converter, value, info):
        # handle separately multivalued attributes
        if isinstance(value, (types.ListType, types.TupleType)):
            result = []
            for elem in value:
                result.append(converter.toLDAPValue(elem, info))
            return result
        else:
            return converter.toLDAPValue(value, info)
