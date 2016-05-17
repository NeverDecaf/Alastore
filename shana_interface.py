from requests import session
from lxml import html as lxmlhtml

# defines several methods for interacting with your shanaproject mylist because there is no official api.
class ShanaLink:
    LOGIN_URL = 'https://www.shanaproject.com/login/'
    LIST_URL = 'http://www.shanaproject.com/follows/list/'
    DELETE_URL = 'http://www.shanaproject.com/ajax/delete_follow/'

    LOGGED_IN_XPATH = "//a[@href='/logout/']"
    
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.SESSION = session()
        self.login()

    # Returns true on successful login or false otherwise
    def login(self):
        response = self.SESSION.get(self.LOGIN_URL)
        etree = lxmlhtml.fromstring(response.text)
        if etree.xpath(self.LOGGED_IN_XPATH):
            return True
        self.csrftoken = self.SESSION.cookies['csrftoken']
        data = {
            'next': '',
            'username': self.username,
            'password': self.password,
            'csrfmiddlewaretoken': self.csrftoken,
            }
        response = self.SESSION.post(self.LOGIN_URL, data = data, headers = dict(Referer = self.LOGIN_URL))
        etree = lxmlhtml.fromstring(response.text)
        return not not etree.xpath(self.LOGGED_IN_XPATH)

    # Deletes a follow by series name. NAME MUST BE EXACT (including caps)
    # Returns True on success, False otherwise.
    def delete_follow(self, name):
        if not self.login():
            return False
        # generate an xpath to match the name of the follow:
        match_name = "//tr[td/a/strong/text()='%s']/@id"%name
        response = self.SESSION.get(self.LIST_URL)
        etree = lxmlhtml.fromstring(response.text)
        follow_id = etree.xpath(match_name)
        if follow_id:
            #do the delete
            data = {
                    'id': follow_id[0][3:],
                    'csrfmiddlewaretoken': self.csrftoken,
                    }
            response = self.SESSION.post(self.DELETE_URL, data=data, headers = dict(Referer=self.LIST_URL))
            if response.text == 'ok':
                return True
        return False
