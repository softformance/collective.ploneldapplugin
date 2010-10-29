""" Plone LDAP Settings GenericSetup support
"""
import types

from Acquisition import aq_base
from ZPublisher.HTTPRequest import default_encoding

from zope.component import adapts, queryUtility, queryMultiAdapter
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent, ObjectModifiedEvent, \
    ObjectCreatedEvent
from zope.app.container.contained import ObjectRemovedEvent

from Products.CMFPlone.utils import safe_unicode
from Products.GenericSetup.interfaces import ISetupEnviron, IBody
from Products.GenericSetup.utils import XMLAdapterBase

from plone.app.ldap.engine.interfaces import ILDAPConfiguration, ILDAPBinding, \
    ILDAPServerConfiguration, ILDAPPropertyConfiguration
from plone.app.ldap.engine.schema import LDAPProperty
from plone.app.ldap.engine.server import LDAPServer
from plone.app.ldap.ploneldap.util import getLDAPPlugin


CACHE_MAPPING = {
    'auth_cache_seconds': 'authenticated',
    'anon_cache_seconds': 'anonymous',
    'negative_cache_seconds': 'negative'
}


class PloneLDAPSettingsXMLAdapter(XMLAdapterBase):
    """ XML im/exporter for Plone LDAP settings
    """

    adapts(ILDAPConfiguration, ISetupEnviron)

    _LOGGER_ID = name = 'ploneldap'
    _encoding = 'utf-8'

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        # prepare root node
        node = self._doc.createElement('object')
        node.appendChild(self._extractGlobalSettings())
        node.appendChild(self._extractLDAPServers())
        node.appendChild(self._extractLDAPSchema())
        node.appendChild(self._extractCacheSettings())

        self._logger.info('Plone LDAP settings exported.')
        return node

    def _importNode(self, node):
        """Import the object from the DOM node"""
        if self.environ.shouldPurge():
            self._purgeSettings()

        # this is important to have schema setup before global settings setup
        # because some of the global settings may reference schema fields
        self._initLDAPServers(node)
        self._initGlobalSettings(node)
        self._initLDAPSchema(node)
        self._initCacheSettings(node)

        self._logger.info('Plone LDAP settings imported.')

    def _purgeSettings(self):
        """Purge all settings before applying them"""
        pass

    def _extractGlobalSettings(self):
        """Read settings from the plone ldap utility"""
        schema = self.context.schema
        fragment = self._doc.createDocumentFragment()
        
        for fname in ILDAPBinding:
            node = self._doc.createElement('property')
            node.setAttribute('name', fname)
            value = getattr(self.context, fname)

            # process value in some special cases
            if fname in ('userid_attribute', 'login_attribute',
                         'rdn_attribute'):
                if value not in schema.keys():
                    continue
                value = schema[value].ldap_name

            node.appendChild(self._doc.createTextNode(self._toString(value)))
            fragment.appendChild(node)

        return fragment

    def _extractLDAPServers(self):
        """Extract LDAP server information"""
        fragment = self._doc.createDocumentFragment()
        servers = self.context.servers.values()

        if len(servers) > 0:
            node = self._doc.createElement('servers')
            for server in servers:
                child = self._doc.createElement('server')
                for fname in ILDAPServerConfiguration:
                    value = self._toString(getattr(server, fname))
                    child.setAttribute(fname, value)
                node.appendChild(child)
            fragment.appendChild(node)

        return fragment

    def _extractLDAPSchema(self):
        """Extract LDAP schema information"""
        fragment = self._doc.createDocumentFragment()
        schema = self.context.schema.values()
        
        if len(schema) > 0:
            node = self._doc.createElement('schema')
            for schema_item in schema:
                child = self._doc.createElement('schema-item')
                for fname in ILDAPPropertyConfiguration:
                    value = self._toString(getattr(schema_item, fname))
                    child.setAttribute(fname, value)
                node.appendChild(child)
            fragment.appendChild(node)

        return fragment

    def _extractCacheSettings(self):
        """Extract ldap cache settings"""
        fragment = self._doc.createDocumentFragment()
        node = self._doc.createElement('cache-settings')
        luf = getLDAPPlugin()._getLDAPUserFolder()

        for cache_value_name, cache_type in CACHE_MAPPING.items():
            child = self._doc.createElement('property')
            child.setAttribute('name', cache_value_name)
            value = luf.getCacheTimeout(cache_type)
            child.appendChild(self._doc.createTextNode(self._toString(value)))
            node.appendChild(child)
        fragment.appendChild(node)

        return fragment

    def _initGlobalSettings(self, node):
        """Apply global settings from the export to a plone ldap utility"""
        # firstly get mapping of ldap properties
        props = {}
        schema = self.context.schema
        for pid, prop in schema.items():
            props[prop.ldap_name] = pid
        
        updated = False
        for child in node.childNodes:
            if child.nodeName != 'property':
                continue

            attr_name = child.getAttribute('name')
            if attr_name not in ILDAPConfiguration:
                continue
            
            # special value processing
            # attributes that reference ldap schema properties
            value = self._getNodeText(child)
            if attr_name in ('rdn_attribute', 'userid_attribute',
                             'login_attribute'):
                if value not in props:
                    continue
                value = props[value]
            # scope attributes
            elif attr_name in ('user_scope', 'group_scope'):
                value = int(value)
            # unicode attributes
            elif attr_name in ('ldap_type',):
                value = safe_unicode(value)
            
            setattr(self.context, attr_name, value)
            updated = True
        
        if updated:
            notify(ObjectModifiedEvent(self.context))

    def _initLDAPServers(self, node):
        """Initialize LDAP servers configurations"""
        # collect existing servers
        servers = {}
        storage = self.context.servers
        for sid, server in storage.items():
            servers[(server.server, server.port)] = sid

        for child in node.childNodes:
            if child.nodeName != 'servers':
                continue

            # if to purge existing servers
            purge = self._convertToBoolean(child.getAttribute('purge') or '0')
            if purge and servers:
                storage.__init__()
                storage._p_changed = True
                servers = {}

            for gchild in child.childNodes:
                if gchild.nodeName != 'server':
                    continue
                
                # create server object from a given properties
                get = gchild.getAttribute
                enabled = self._convertToBoolean(get('enabled') or 'False')
                host = get('server')
                connection_type = int(get('connection_type'))
                operation_timeout = int(get('operation_timeout'))
                connection_timeout = int(get('connection_timeout'))
                server = LDAPServer(
                    server=host,
                    connection_type=connection_type,
                    connection_timeout=connection_timeout,
                    operation_timeout=operation_timeout,
                    enabled=enabled)
                server_key = (server.server, server.port)
                
                # remove="True" in xml file to delete server
                remove = self._convertToBoolean(get('remove') or 'false')
                if remove:
                    if server_key in servers:
                        notify(ObjectRemovedEvent(servers[server_key]))
                        del storage[servers[server_key]]
                        del servers[server_key]
                else:
                    if server_key in servers:
                        del storage[servers[server_key]]
                        storage[servers[server_key]] = server
                        notify(ObjectModifiedEvent(server))
                    else:
                        storage.addItem(server)
                        notify(ObjectCreatedEvent(server))

    def _initLDAPSchema(self, node):
        """Initialize LDAP schema information"""
        # firstly get mapping of ldap properties
        props = {}
        schema = self.context.schema
        for pid, prop in schema.items():
            props[prop.ldap_name] = pid
        
        for child in node.childNodes:
            if child.nodeName != 'schema':
                continue

            # if to purge schema properties
            purge = self._convertToBoolean(child.getAttribute('purge') or '0')
            if purge and props:
                schema.__init__()
                schema._p_changed = True
                props = {}

            for gchild in child.childNodes:
                if gchild.nodeName != 'schema-item':
                    continue

                get = gchild.getAttribute
                ldap_name = get('ldap_name')
                # remove="True" in xml file to delete property from ldap schema
                remove = self._convertToBoolean(get('remove') or 'false')
                if remove:
                    if ldap_name in props:
                        notify(ObjectRemovedEvent(schema[props[ldap_name]]))
                        del schema[props[ldap_name]]
                        del props[ldap_name]
                else:
                    # TODO: add 'binary' attribute to property when this is
                    #       implemented by plone.app.ldap package
                    prop = LDAPProperty(
                        ldap_name=ldap_name,
                        plone_name=get('plone_name') or '',
                        description=safe_unicode(get('description') or ''),
                        multi_valued=self._convertToBoolean(get('multi_valued'))
                    )                        
                    if ldap_name in props:
                        del schema[props[ldap_name]]
                        schema[props[ldap_name]] = prop
                        notify(ObjectModifiedEvent(prop))
                    else:
                        schema.addItem(prop)
                        notify(ObjectCreatedEvent(prop))

    def _initCacheSettings(self, node):
        """Initialize cache settings"""
        luf = getLDAPPlugin()._getLDAPUserFolder()
        
        for child in node.childNodes:
            if child.nodeName != 'cache-settings':
                continue
            
            for gchild in child.childNodes:
                if gchild.nodeName != 'property':
                    continue
                
                value = self._getNodeText(gchild)
                attr_name = gchild.getAttribute('name')
                if attr_name in CACHE_MAPPING:
                    luf.setCacheTimeout(cache_type=CACHE_MAPPING[attr_name],
                                        timeout=int(value))

    def _toString(self, value):
        if not isinstance(value, types.StringTypes):
            value = str(value)
        elif isinstance(value, unicode):
            value = value.encode(self._encoding)
        return value

def importPloneLDAPSettings(context):
    """Import Plone LDAP settings from an XML file
    """
    site = context.getSite()
    storage = queryUtility(ILDAPConfiguration)
    if storage is not None:
        importer = queryMultiAdapter((storage, context), IBody)
        if importer:
            filename = '%s%s' % (importer.name, importer.suffix)
            body = context.readDataFile(filename)
            if body is not None:
                importer.filename = filename # for error reporting
                importer.body = body
    else:
        context.getLogger('ploneldap').debug('Nothing to import.')

def exportPloneLDAPSettings(context):
    """Export Plone LDAP settings from an XML file
    """
    site = context.getSite()
    storage = queryUtility(ILDAPConfiguration)
    if storage is not None:
        exporter = queryMultiAdapter((storage, context), IBody)
        if exporter:
            filename = '%s%s' % (exporter.name, exporter.suffix)
            body = exporter.body
            if body is not None:
                context.writeDataFile(filename, body, exporter.mime_type)
    else:
        context.getLogger('ploneldap').debug('Nothing to export.')
