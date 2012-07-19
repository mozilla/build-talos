"""
A class to interact with AMO's api, using OAuth.
Ripped off from Daves test_oauth.py and some notes from python-oauth2
"""

import httplib2
import mimetools
import os
import re
import urllib
import urllib2
import time

import oauth2 as oauth

from urlparse import urlparse, urlunparse
from cgi import parse_qsl

try:
    import json
except ImportError:
    import simplejson as json

from amo_utils import encode_multipart, data_keys

# AMO Specific end points
urls = {
    'login': '/users/login',
    'request_token': '/oauth/request_token/',
    'access_token': '/oauth/access_token/',
    'authorize': '/oauth/authorize/',
    'user': '/api/2/user/',
    'addon': '/api/2/addons/',
    'versions': '/api/2/addon/%s/versions',
    'version': '/api/2/addon/%s/version/%s',
    'perf': '/api/2/performance/add',
    'perf_os': '/api/2/performance/os/',
    'perf_app': '/api/2/performance/app/',
}

storage_file = os.path.join(os.path.expanduser('~'), '.amo-oauth')
boundary = mimetools.choose_boundary()

class AMOOAuth:
    """
    A base class to authenticate and work with AMO OAuth.
    """
    signature_method = oauth.SignatureMethod_HMAC_SHA1()

    def __init__(self, domain='addons.mozilla.org', protocol='https',
                 port=443, prefix='', three_legged=False):
        self.data = self.read_storage()
        self.domain = domain
        self.protocol = protocol
        self.port = port
        self.prefix = prefix
        self.three_legged = three_legged

    def set_consumer(self, consumer_key, consumer_secret):
        self.data['consumer_key'] = consumer_key
        self.data['consumer_secret'] = consumer_secret
        self.save_storage()

    def get_consumer(self):
        return oauth.Consumer(self.data['consumer_key'],
                              self.data['consumer_secret'])

    def get_access(self):
        return oauth.Token(self.data['access_token']['oauth_token'],
                           self.data['access_token']['oauth_token_secret'])

    def has_access_token(self):
        return not self.three_legged or 'access_token' in self.data

    def read_storage(self):
        if os.path.exists(storage_file):
            try:
                return json.load(open(storage_file, 'r'))
            except ValueError:
                pass
        return {}

    def url(self, key, *args):
        args = '/'.join([str(a) for a in args])
        if args:
            args = '%s' % args
        return urlunparse((self.protocol, '%s:%s' % (self.domain, self.port),
                           '%s/en-US/firefox%s%s' %
                           (self.prefix, urls[key], args),
                           '', '', ''))

    def shorten(self, url):
        return urlunparse(['', ''] + list(urlparse(url)[2:]))

    def save_storage(self):
        json.dump(self.data, open(storage_file, 'w'))

    def get_csrf(self, content):
        return re.search("name='csrfmiddlewaretoken' value='(.*?)'",
                         content).groups()[0]

    def _request(self, token, method, url, data={}, headers={}, **kw):
        parameters = data_keys(data)
        parameters.update(kw)
        request = (oauth.Request
                        .from_consumer_and_token(self.get_consumer(), token,
                                                 method, url, parameters))
        request.sign_request(self.signature_method, self.get_consumer(), token)
        client = httplib2.Http(disable_ssl_certificate_validation=True)
        if data and method in ['POST', 'PUT']:
            data = encode_multipart(boundary, data)
            headers.update({'Content-Type':
                            'multipart/form-data; boundary=%s' % boundary})
        else:
            data = urllib.urlencode(data)
        return client.request(request.to_url(), method=method,
                              headers=headers, body=data)

    def authenticate(self, username=None, password=None):
        """
        This is only for the more convoluted three legged approach.
        1. Login into AMO.
        2. Get a request token for the consumer.
        3. Approve the consumer.
        4. Get an access token.
        """
        # First we need to login to AMO, this takes a few steps.
        # If this was being done in a browser, this wouldn't matter.
        #
        # This callback is pretty academic, but required so we can get
        # verification token.
        callback = 'http://foo.com/'

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        urllib2.install_opener(opener)
        res = opener.open(self.url('login'))
        assert res.code == 200

        # get the CSRF middleware token
        if password is None:
            password = raw_input('Enter password: ')

        csrf = self.get_csrf(res.read())
        data = urllib.urlencode({'username': username,
                                 'password': password,
                                 'csrfmiddlewaretoken': csrf})
        res = opener.open(self.url('login'), data)
        assert res.code == 200

        # We need these headers to be able to post to the authorize method
        cookies = {}
        # Need to find a better way to find the handler, -2 is fragile.
        for cookie in opener.handlers[-2].cookiejar:
            if cookie.name == 'sessionid':
                cookies = {'Cookie': '%s=%s' % (cookie.name, cookie.value)}
        # Step 1 completed, we can now be logged in for any future requests

        # Step 2, get a request token.
        resp, content = self._request(None, 'GET', self.url('request_token'),
                                      oauth_callback=callback)
        assert resp['status'] == '200', 'Status was: %s' % resp.status

        request_token = dict(parse_qsl(content))
        assert request_token
        token = oauth.Token(request_token['oauth_token'],
                            request_token['oauth_token_secret'])

        # Step 3, authorize the access of this consumer for this user account.
        resp, content = self._request(token, 'GET', self.url('authorize'),
                                      headers=cookies)
        csrf = self.get_csrf(content)
        data = {'authorize_access': True,
                'csrfmiddlewaretoken': csrf,
                'oauth_token': token.key}
        resp, content = self._request(token, 'POST', self.url('authorize'),
                                      headers=cookies, data=data,
                                      oauth_callback=callback)

        assert resp.status == 302, 'Status was: %s' % resp.status
        qsl = parse_qsl(resp['location'][len(callback) + 1:])
        verifier = dict(qsl)['oauth_verifier']
        token.set_verifier(verifier)

        # We have now authorized the app for this user.
        resp, content = self._request(token, 'GET', self.url('access_token'))
        access_token = dict(parse_qsl(content))
        self.data['access_token'] = access_token
        self.save_storage()
        # Done. Wasn't that fun?

    def get_params(self):
        return dict(oauth_consumer_key=self.data['consumer_key'],
                    oauth_nonce=oauth.generate_nonce(),
                    oauth_signature_method='HMAC-SHA1',
                    oauth_timestamp=int(time.time()),
                    oauth_version='1.0')

    def _send(self, url, method, data):
        resp, content = self._request(None, method, url,
                                      data=data)
        if resp.status not in [200, 201]:
            raise ValueError('%s: %s' % (resp.status, content))
        try:
            return json.loads(content)
        except ValueError:
            return content

    def get_user(self):
        return self._send(self.url('user'), 'GET', {})

    def create_addon(self, data):
        return self._send(self.url('addon'), 'POST', data)

    def create_version(self, data, id):
        return self._send(self.url('version') % id, 'POST', data)

    def get_versions(self, addon_id):
        return self._send(self.url('versions') % addon_id, 'GET', {})

    def get_version(self, addon_id, version_id):
        return self._send(self.url('version') % (addon_id, version_id),
                          'GET', {})

    def create_perf(self, data):
        return self._send(self.url('perf'), 'POST', data)

    def update_perf(self, data, id):
        return self._send(self.url('perf', id), 'PUT', data)

    # TODO(andym): something more funky with getattr, this could get boring
    def create_app(self, data):
        return self._send(self.url('perf_app'), 'POST', data)

    def update_app(self, data, id):
        return self._send(self.url('perf_app', id), 'PUT', data)

    def list_app(self):
        return self._send(self.url('perf_app'), 'GET', {})

    def create_os(self, data):
        return self._send(self.url('perf_os'), 'POST', data)

    def update_os(self, data, id):
        return self._send(self.url('perf_os', id), 'PUT', data)

    def list_os(self):
        return self._send(self.url('perf_os'), 'GET', {})


if __name__ == '__main__':
    username = 'amckay@mozilla.com'
    amo = AMOOAuth(domain="addons.mozilla.local", port=8000, protocol='http')
    amo.set_consumer(consumer_key='CmAn9KhXR8SD3xUSrf',
                     consumer_secret='4hPsAW9yCecr4KRSR4DVKanCkgpqDETm')
    if not amo.has_access_token():
        # This is an example, don't get too excited.
        amo.authenticate(username=username)
    print amo.get_user()
