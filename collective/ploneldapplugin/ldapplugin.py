import logging
from ldap import schema

from zope.interface import implementedBy, classImplements

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Acquisition import aq_base
from persistent.mapping import PersistentMapping

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.PloneLDAP.plugins.ldap import PloneLDAPMultiPlugin
from Products.PloneLDAP.factory import genericPluginCreation

from collective.ploneldapplugin.ldapproperty import EnhancedLDAPPropertySheet
from collective.ploneldapplugin import logException


manage_addEnhancedPloneLDAPMultiPluginForm = PageTemplateFile(
    "www/addEnhancedLdapPlugin", globals())

def manage_addEnhancedPloneLDAPMultiPlugin(self, id, title, LDAP_server,
    login_attr, uid_attr, users_base, users_scope, roles, groups_base,
    groups_scope, binduid, bindpwd, binduid_usage=1, rdn_attr='cn',
    local_groups=0, use_ssl=0, encryption='SHA', read_only=0, REQUEST=None):
    """Add an Enhanced Plone LDAP plugin to the site"""

    luf = genericPluginCreation(self, EnhancedPloneLDAPMultiPlugin, id=id,
        title=title, login_attr=login_attr, uid_attr=uid_attr,
        users_base=users_base, users_scope=users_scope, roles=roles,
        groups_base=groups_base, groups_scope=groups_scope, binduid=binduid,
        bindpwd=bindpwd, binduid_usage=binduid_usage, rdn_attr=rdn_attr,
        local_groups=local_groups, use_ssl=use_ssl, encryption=encryption,
        read_only=read_only, LDAP_server=LDAP_server, REQUEST=None)

    luf._ldapschema["cn"]["public_name"]="fullname"
    luf.manage_addLDAPSchemaItem("mail", "Email Address", public_name="email")

    # Redirect back to the user folder
    if REQUEST is not None:
        return REQUEST["RESPONSE"].redirect(
            "%s/manage_workspace?manage_tabs_message=Enhanced+LDAP"
            "+Multi+Plugin+added" %self.absolute_url())

class EnhancedPloneLDAPMultiPlugin(PloneLDAPMultiPlugin):
    """Enhanced Plone LDAP plugin.
    """
    security = ClassSecurityInfo()
    meta_type = "Enhanced Plone LDAP plugin"

    security.declarePrivate('getLDAPAttrs')
    def getLDAPAttrs(self):
        """Return LDAP Schema Attributes Mapping:
        
        {
          (ldapname, zopename, type): (Attribute, Syntax OID),
        }
        """
        # add attribute if needed
        if not hasattr(aq_base(self), '_ldapattrs'):
            self._ldapattrs = PersistentMapping()
        
        # fill it in if it's empty
        if not self._ldapattrs:
            acl = self._getLDAPUserFolder()
            meta = self._getLDAPMetaData(acl)
            if meta:
                for info in acl.getSchemaConfig().values():
                    ldapname, zopename, type = (info['ldap_name'],
                        info['public_name'], info['multivalued'] and 'lines' or
                        'string')
                    if not zopename or not meta.has_key(ldapname):
                        continue
                    self._ldapattrs[(ldapname, zopename, type)] = meta[ldapname]
        
        return self._ldapattrs

    def _getLDAPMetaData(self, acl):
        """Return ldap attributes metadata
        
        {
          ldapname: (attribute, syntax oid),
        }
        """
        try:
            connection = acl._delegate.connect()
            subentrydn = connection.search_subschemasubentry_s()
            entry = connection.read_subschemasubentry_s(subentrydn)
            subschema = schema.SubSchema(entry)
            must, may = subschema.attribute_types(acl._user_objclasses)
        except Exception, e:
            logException(u"Error while trying to gather LDAP Attributes Schema"
                         " Metadata", acl)
            return {}
        
        # gets attribute type syntax oid recursively if needed
        def _get_syntax_oid(attr, default=None):
            oid = attr.syntax
            if not oid:
                for sup in attr.sup:
                    parent = subschema.get_inheritedobj(schema.AttributeType,
                        sup)
                    oid = _get_syntax_oid(parent, default)
            return oid or default
        
        data = {}
        for attribute in must.values() + may.values():
            oid = _get_syntax_oid(attribute)            
            for name in attribute.names:
                data[name] = (attribute, oid)
        return data

    security.declarePrivate('getPropertiesForUser')
    def getPropertiesForUser(self, user, request=None):
        """Fullfill PropertiesPlugin requirements"""
        try:
            return EnhancedLDAPPropertySheet(self.id, user)
        except KeyError:
            return None

    security.declarePrivate('setPropertiesForUser')
    def setPropertiesForUser(self, user, propertysheet):
        """Use here propertysheet API thus avoiding code duplication"""
        propertysheet.setProperties(user, propertysheet._properties)

classImplements(EnhancedPloneLDAPMultiPlugin,
    *implementedBy(PloneLDAPMultiPlugin))

InitializeClass(EnhancedPloneLDAPMultiPlugin)
