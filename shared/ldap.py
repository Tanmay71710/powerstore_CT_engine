from ldap3 import ALL, Connection, Server, Tls
import ssl
import time
import vaultInteraction.vaultInteraction as vi

tls = Tls(ciphers="ALL", version=ssl.PROTOCOL_SSLv23, validate=ssl.CERT_NONE)
from ldap3.core.exceptions import LDAPInvalidCredentialsResult, LDAPSocketOpenError

ldap_ip = "ldaps://amer.dell.com:3269"
root_dn = "CN=svc_prdsysqafw,OU=Service Accounts,DC=amer,DC=dell,DC=com"
base_dn = "DC=dell,DC=com"
user_by_email = {'tri.ww.bpt.services@dell.com': 'svc_prdpstorejirasup'} #TO-DO remove once we update the ldap server


class Ldap:
    def __init__(self):
        self.ldap_ip = ldap_ip
        self.root_dn = root_dn
        self.root_password = vi.get_safe_object('SYSQA_GITHUB_PASSWORD')

    def get_client(self):
        """
        Get LDAP client
        """
        server = Server(self.ldap_ip, get_info=ALL, use_ssl=True, tls=tls, connect_timeout=10)
        err = None
        for _ in range(2):
            try:
                return Connection(server, self.root_dn, self.root_password, auto_bind=True)
            except LDAPSocketOpenError as e:
                err = e
                time.sleep(2)
        raise err


    def search_ldap(self, searchFilter):
        """
        Query ldap server by given filter

        :param searchFilter: search filter
        :type searchFilter: str
        :return: user info
        :rtype: ldap3.abstract.entry.Entry
        """
        client = self.get_client()
        try:
            attributes = ['cn', 'sAMAccountName',"mail"]

            client.search(base_dn, searchFilter, attributes=attributes, time_limit=5)

            if not client.entries:
                raise ValueError("User not found")

            return client.entries[0]
        finally:
            client.unbind()

    def search_user_by_username(self, username):
        """
        ldap search by username

        :param username: username
        :type username: str
        :return: user info
        :rtype: ldap3.abstract.entry.Entry
        """
        searchFilter = f'(&(objectClass=user)(sAMAccountName={username}))'
        return self.search_ldap(searchFilter)

    def search_user_by_cn(self, common_name):
        search_filter = f'(&(objectClass=user)(cn={common_name}))'
        return self.search_ldap(search_filter)

    def authenticate_user(self, username, password):
        """
        ldap authentication

        :param username: username
        :type username: str
        :param password: user password
        :type password: str
        :return: True for successful authentication OW False
        :rtype: bool
        """
        user_entry = self.search_user_by_username(username)  # Get the user's entry
        user_dn = user_entry.entry_dn  # Get the user's distinguished name (DN)

        # Now try to bind as this user with the provided password
        server = Server(self.ldap_ip, get_info=ALL, use_ssl=True, tls=tls, connect_timeout=10)
        user_client = Connection(server, user_dn, password)

        try:
            if user_client.bind():
                return True
            else:
                raise LDAPInvalidCredentialsResult("Authentication failed: Incorrect username or password.")
        finally:
            user_client.unbind()  # Ensure to unbind even if binding fails
