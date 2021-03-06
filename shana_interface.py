from requests import session
from lxml import html as lxmlhtml
from urllib.parse import urljoin
from constants import *
# defines several methods for interacting with your shanaproject mylist because there is no official api.
class ShanaLink:

    def __init__(self, username = '', password = ''):
        self.username = username
        self.password = password
        self.SESSION = session()
##        self._login()

    def update_creds(self, username, password):
        if not (username == self.username and password == self.password):
            self.SESSION = session()
            self.username = username
            self.password = password
        
    # Returns true on successful login or false otherwise
    def _login(self):
        response = self.SESSION.get(SP_LOGIN_URL)
        etree = lxmlhtml.fromstring(response.text)
        if etree.xpath(SP_LOGGED_IN_XPATH):
            return True
        self.csrftoken = self.SESSION.cookies['csrftoken']
        data = {
            'next': '',
            'username': self.username,
            'password': self.password,
            'csrfmiddlewaretoken': self.csrftoken,
            }
        response = self.SESSION.post(SP_LOGIN_URL, data = data, headers = dict(Referer = SP_LOGIN_URL))
        etree = lxmlhtml.fromstring(response.text)
        return not not etree.xpath(SP_LOGGED_IN_XPATH)

    # Deletes a follow by series name. NAME MUST BE EXACT (including caps)
    # Returns True on success, False otherwise.
    def delete_follow(self, name):
        if not self._login():
            return False
        # generate an xpath to match the name of the follow:
##        match_name = '//tr[td//text()="%s"]/@id'%name
        match_name = "//tr[td//text()=concat('','{}')]/@id".format('\',"\'",\''.join(name.split("'")).strip(','))
        next_page = "//div[@class='grid_2 list_next']//a/@href"
        url = SP_LIST_URL
        while url:
            response = self.SESSION.get(url)
            etree = lxmlhtml.fromstring(response.text)
            follow_id = etree.xpath(match_name)
            if follow_id:
                #do the delete
                data = {
                        'id': follow_id[0][3:],
                        'csrfmiddlewaretoken': self.csrftoken,
                        }
                response = self.SESSION.post(SP_DELETE_URL, data=data, headers = dict(Referer=SP_LIST_URL))
                if response.text == 'ok':
                    return True
            try:
                url = urljoin(url, etree.xpath(next_page)[0])
            except IndexError:
                break
        return False
