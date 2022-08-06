import sys
import time
import uuid

import jwt  # type: ignore

from typing import Sequence, Dict, List, Union
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.registration import Registration
from typing_extensions import Literal
from mypy_extensions import TypedDict

_DeepLinkData = TypedDict(
    '_DeepLinkData',
    {
        # Required data:
        'deep_link_return_url': str,
        'accept_types': List[Literal['link', 'ltiResourceLink']],
        'accept_presentation_document_targets': List[ Literal['iframe', 'window', 'embed']],
        # Optional data
        'accept_multiple': Union[bool, Literal['true', 'false']],
        'auto_create': Union[bool, Literal['true', 'false']],
        'title': str,
        'text': str,
        'data': object,
    },
    total=False,
)


class DeepLink(object):

    def __init__(self, registration: Registration, deployment_id: str, deep_link_settings: _DeepLinkData) -> None:
        self._registration: Registration = registration
        self._deployment_id: str = deployment_id
        self._deep_link_settings: _DeepLinkData = deep_link_settings

    def _generate_nonce(self) -> str:
        return uuid.uuid4().hex + uuid.uuid1().hex

    def get_message_jwt(self, resources: Sequence[DeepLinkResource]) -> Dict[str, object]:
        message_jwt = {
            'iss': self._registration.get_client_id(),
            'aud': [self._registration.get_issuer()],
            'exp': int(time.time()) + 600,
            'iat': int(time.time()),
            'nonce': 'nonce-' + self._generate_nonce(),
            'https://purl.imsglobal.org/spec/lti/claim/deployment_id': self._deployment_id,
            'https://purl.imsglobal.org/spec/lti/claim/message_type': 'LtiDeepLinkingResponse',
            'https://purl.imsglobal.org/spec/lti/claim/version': '1.3.0',
            'https://purl.imsglobal.org/spec/lti-dl/claim/content_items': [r.to_dict() for r in resources],
            'https://purl.imsglobal.org/spec/lti-dl/claim/data': self._deep_link_settings.get('data')
        }
        return message_jwt

    def encode_jwt(self, message):
        headers = None
        kid = self._registration.get_kid()
        if kid:
            headers = {'kid': kid}
        encoded_jwt = jwt.encode(message, self._registration.get_tool_private_key(), algorithm='RS256', headers=headers)
        if sys.version_info[0] > 2 and isinstance(encoded_jwt, bytes):
            return encoded_jwt.decode('utf-8')
        return encoded_jwt

    def get_response_jwt(self, resources: Sequence[DeepLinkResource]) -> str:
        message_jwt = self.get_message_jwt(resources)
        return self.encode_jwt(message_jwt)

    def get_response_form_html(self, jwt_val: str) -> str:
        html = '<form id="lti13_deep_link_auto_submit" action="%s" method="POST">' \
               '<input type="hidden" name="JWT" value="%s" /></form>' \
               '<script type="text/javascript">document.getElementById(\'lti13_deep_link_auto_submit\').submit();' \
               '</script>' % (self._deep_link_settings['deep_link_return_url'], jwt_val)
        return html

    def output_response_form(self, resources: Sequence[DeepLinkResource]) -> None:
        jwt_val = self.get_response_jwt(resources)
        return self.get_response_form_html(jwt_val)
