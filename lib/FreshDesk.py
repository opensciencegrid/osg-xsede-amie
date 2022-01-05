#!/usr/bin/python3

import json
import logging
import pprint
import requests

log = logging.getLogger('osgxsede')


class FreshDesk():
    config = None

    def __init__(self, config):
        self.config = config

    def open_ticket(self, subject, body):
        ticket = {
            'subject': subject,
            'description': body,
            'email': self.config.get('freshdesk', 'opened_by_email'),
            'priority': 1,
            'status': 2,
            'type': 'Other'
        }
        headers = {'Content-Type': 'application/json'}

        if len(self.config.get('freshdesk', 'url')) > 0:
            url_request = requests.post(self.config.get('freshdesk', 'url'),
                                        data=json.dumps(ticket),
                                        auth=(self.config.get('freshdesk', 'api_key'), 'x'),
                                        headers=headers)
            if url_request.status_code in [200, 201]:
                json_return = url_request.json()
                log.info('Created Ticket {}'.format(json_return['id']))
        else:
            log.warning('Not opening ticket as Freshdesk URL is not defined. Here is the ticket:')
            log.warning(pprint.pformat(ticket, indent=4))
