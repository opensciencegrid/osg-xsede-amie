#!/usr/bin/python3

import configparser
import logging
import re
import time
import pprint
from logging.config import dictConfig

from AMIE import AMIE
from FreshDesk import FreshDesk
from GRACC import GRACC, GRACCState

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "fmt": "%(levelprefix)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",

        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "osgxsede": {"handlers": ["default"], "level": "DEBUG"},
    }
}

dictConfig(log_config)
log = logging.getLogger('osgxsede')


class Main():
    config = None
    amie = None
    connect = None
    freshdesk = None

    def __init__(self):

        log.info('Reading config from /opt/apps/osg-xsede-amie/etc/osg-xsede-amie.conf')
        self.config = configparser.ConfigParser()
        self.config.read('/opt/apps/osg-xsede-amie/etc/osg-xsede-amie.conf')

        self.amie = AMIE(self.config)
        self.freshdesk = FreshDesk(self.config)

    def request_project_create(self, packet):

        # Eventually, we should be able to automatically process requests for
        # exiting PIs (packet.PiPersonID in OSGConnect), but we have to wait
        # for this until we have fully transitioned from xd-login

        grant_number = packet.GrantNumber
        record_id = packet.RecordID
        project_id = packet.ProjectID  # site project_id (if known)
        request_type = packet.RequestType
        allocation_type = packet.AllocationType  # new, renewal, supplement, transfer, adjustment, advance, extension, ...
        start_date = packet.StartDate
        end_date = packet.EndDate
        amount = packet.ServiceUnitsAllocated
        abstract = packet.Abstract
        project_title = packet.ProjectTitle
        board_type = packet.BoardType
        pfos_num = packet.PfosNumber

        pi_person_id = packet.PiPersonID  # site person_id for the PI (if known)
        pi_first_name = packet.PiFirstName
        pi_middle_name = packet.PiMiddleName
        pi_last_name = packet.PiLastName
        pi_organization = packet.PiOrganization
        pi_department = packet.PiDepartment
        pi_email = packet.PiEmail
        pi_phone_number = packet.PiBusinessPhoneNumber
        pi_nsf_status_code = packet.NsfStatusCode

        subject = f'New XSEDE project: TG-{grant_number}'
        body = f'''<p>A new project has been received from XSEDE. OSG Facilitators should perform the
following steps to ensure the required projects and users already exists / have been created:</p>

<br/>
<ol>
  <li>Search OSGConnect for the PI and project.
  <li>If the PI does not have an account, use the XSEDE FreshDesk template to ask the PI to request an OSGConnect account.
  <li>Make sure that the two required projects exists (TG-{grant_number}, and Inst_PILastname)
</ol>

<br/>
<p>Once these steps are complete, respond to this ticket and assign to Mats.</p>

<br/>
<p>
Project: TG-{grant_number}<br/>
Title: {project_title}<br/>
Abstract: {abstract}<br/>
</p>

<br/>
<p>
PI: {pi_first_name} {pi_last_name}<br/>
Organization: {pi_organization}<br/>
Email: {pi_email}<br/>
</p>
'''
        self.freshdesk.open_ticket(subject, body)
        self.amie.save_packet(packet, 'incoming', 'parked')

    def data_project_create(self, packet):
        # the data_project_create(DPC) packet has two functions:
        # 1. to let the site know that the project and PI account have been setup in the XDCDB
        # 2. to provide any new DNs for the PI that were added after the RPC was sent
        # NOTE: a DPC does *not* have the resource. You have to get the resource from the RPC for the trans_rec_id

        person_id = packet.PersonID
        project_id = packet.ProjectID
        dn_list = packet.DnList

        # construct the InformTransactionComplete(ITC) success packet
        itc = packet.reply_packet()
        itc.StatusCode = 'Success'
        itc.DetailCode = '1'
        itc.Message = 'OK'

        # send the ITC
        self.amie.send_packet(itc)

    def request_account_create(self, packet):
        packet.pretty_print()
        grant_number = packet.GrantNumber
        project_id = packet.ProjectID  # site project_id
        resource = packet.ResourceList[0]  # xsede site resource name, eg, delta.ncsa.xsede.org

        user_global_id = packet.UserGlobalID
        user_person_id = packet.UserPersonID  # site person_id for the User (if known)
        user_first_name = packet.UserFirstName
        user_middle_name = packet.UserMiddleName
        user_last_name = packet.UserLastName
        user_organization = packet.UserOrganization
        user_department = packet.UserDepartment
        user_email = packet.UserEmail
        user_phone_number = packet.UserBusinessPhoneNumber
        user_phone_extension = packet.UserBusinessPhoneExtension
        user_address1 = packet.UserStreetAddress
        user_address2 = packet.UserStreetAddress2
        user_city = packet.UserCity
        user_state = packet.UserState
        user_zipcode = packet.UserZip
        user_country = packet.UserCountry
        user_requested_logins = packet.UserRequestedLoginList
        project_id = packet.ProjectID

        # RACs are also used to reactivate accounts, so if the account already exists, just set it active
        if user_person_id and len(user_person_id) > 1:
            try:
                user = self.connect.user(user_person_id)

                # ensure emails match
                if user_email == user['email']:
                    # construct a NotifyAccountCreate(NAC) packet.
                    nac = packet.reply_packet()
                    nac.UserRemoteSiteLogin = user['unix_name']  # local login for the User on the resource
                    nac.UserPersonID = user_person_id  # local person ID for the User
                    self.amie.send_packet(nac)
                    return
            except Exception:
                # unable to find/process the user - fall back to facilitators
                pass

        subject = f'New XSEDE account: {user_first_name} {user_last_name}'
        body = f'''<p>A new account request has been received from XSEDE. OSG Facilitators should perform the
following steps to ensure the required user already exists / have been created:</p>

<br/>
<ol>
  <li>Search OSGConnect for the user.
  <li>If the user does not have an account, use the XSEDE FreshDesk template to ask the user to request an OSGConnect account.
  <li>There is no need for creating a project - the user will be automatically assigned later
</ol>

<br/>
<p>Once these steps are complete, respond to this ticket and assign to Mats.</p>

<br/>
<p>
Name: {user_first_name} {user_last_name}<br/>
Organization: {user_organization}<br/>
Email: {user_email}<br/>
XSEDE Project: {project_id}<br/>
XSEDE global ID: {user_global_id}<br/>
</p>
'''
        self.freshdesk.open_ticket(subject, body)
        self.amie.save_packet(packet, 'incoming', 'parked')

    def data_account_create(self, packet):
        # the data_account_create(DAC) packet has two functions:
        # 1. to let the site know that the User account on the project has been setup in the XDCDB
        # 2. to provide any new DNs for the User that were added after the RAC was sent
        # NOTE: a DAC does *not* have the resource. You have to get the resource from the RAC for the trans_rec_id

        # As OSG is no longer doing any X.509, we will ignore the DN updates

        person_id = packet.PersonID
        project_id = packet.ProjectID
        dn_list = packet.DnList

        # construct the InformTransactionComplete(ITC) success packet
        itc = packet.reply_packet()
        itc.StatusCode = 'Success'
        itc.DetailCode = '1'
        itc.Message = 'OK'

        # send the ITC
        self.amie.send_packet(itc)

    def request_account_inactivate(self, packet):
        resource = packet.ResourceList[0]
        project_id = packet.ProjectID
        person_id = packet.PersonID

        log.info('Removing user {} from project {}'.format(person_id, project_id))
        # Disabled for initial switchover from xd-login
        # self.connect.remove_user_from_project(project_id, person_id)

        nai = packet.reply_packet()
        self.amie.send_packet(nai)

    def request_user_modify(self, packet):
        # person_id = packet.person_id
        # if packet.Actiontype == 'delete':
        #     # we are not using DNs anymore
        #     pass
        # else:
        #     first_name = packet.FirstName
        #     last_name = packet.LastName
        #     organization = packet.Organization
        #     department = packet.Department
        #     email = packet.Email
        #     bus_phone_number = packet.BusinessPhoneNumber
        #
        #     #self.connect.update_user(username, ....)

        # construct the InformTransactionComplete(ITC) success packet
        itc = packet.reply_packet()
        itc.StatusCode = 'Success'
        itc.DetailCode = '1'
        itc.Message = 'OK'

        # send the ITC
        self.amie.send_packet(itc)

    def request_person_merge(self, packet):
        raise RuntimeError('request_person_merge not implemented')

    def request_project_inactivate(self, packet):
        resource = packet.ResourceList[0]
        project_id = packet.ProjectID

        log.info('Deactivating {}'.format(project_id))
        try:
            self.connect.remove_all_users(project_id)
        except:
            # project might not exist
            pass

        nai = packet.reply_packet()
        self.amie.send_packet(nai)

    def request_project_reactivate(self, packet):
        resource = packet.ResourceList[0]
        project_id = packet.ProjectID
        pi_person_id = packet.PersonID

        log.info('Reactivating {}'.format(project_id))
        # self.connect.add_uid_to_project(project_id, pi_person_id)

        npr = packet.reply_packet()
        self.amie.send_packet(npr)

    def inform_transaction_complete(self, packet):
        # construct the InformTransactionComplete(ITC) success packet
        itc = packet.reply_packet()
        itc.StatusCode = 'Success'
        itc.DetailCode = '1'
        itc.Message = 'OK'

        # send the ITC
        self.amie.send_packet(itc)

    def main(self):

        while True:

            log.info('Starting new iteration...')

            # count parked packets
            packets = self.amie.load_packets('incoming', 'parked')
            log.info(' ... {} packets are parked and waiting for facilitators'.format(len(packets)))

            # now check the inbox
            packets = self.amie.list()

            if packets is not None:
                log.info(' ... {} packets in the inbox'.format(len(packets)))
                for packet in packets:
                    packet_type = packet.packet_type
                    packet_rec_id = packet.packet_rec_id
                    trans_rec_id = packet.trans_rec_id

                    if self.amie.already_processed(packet):
                        # skip packages we have already processed (or chosen to ignore)
                        continue

                    log.info("Handling new packet: type={} packet_rec_id={} trans_rec_id={}".format(
                        packet_type, packet_rec_id, trans_rec_id
                    ))

                    if packet_type == 'request_project_create':
                        self.request_project_create(packet)
                    elif packet_type == 'data_project_create':
                        self.data_project_create(packet)
                    elif packet_type == 'request_account_create':
                        self.request_account_create(packet)
                    elif packet_type == 'data_account_create':
                        self.data_account_create(packet)
                    elif packet_type == 'request_account_inactivate':
                        self.request_account_inactivate(packet)
                    elif packet_type == 'request_user_modify':
                        self.request_user_modify(packet)
                    elif packet_type == 'request_person_merge':
                        self.request_person_merge(packet)
                    elif packet_type == 'request_project_inactivate':
                        self.request_project_inactivate(packet)
                    elif packet_type == 'request_project_reactivate':
                        self.request_project_reactivate(packet)
                    elif packet_type == 'inform_transaction_complete':
                        self.inform_transaction_complete(packet)
                    else:
                        packet.pretty_print()
                        raise RuntimeError("We do not know how to handle packets of type {}".format(packet_type))

                    # always save a copy
                    self.amie.save_packet(packet, 'incoming', 'received')

            # send in usage information (pull from GRACC)
            q = GRACC(self.config)
            # loop over all the maps defined in the conf file
            for section in self.config.sections():
                if re.match("^graccusage_", section):
                    # we have a valid map
                    try:
                        state = GRACCState(self.config, section)
                        start_time = state.get_ts()
                    except Exception as e:
                        log.error(e)
                        log.error('Unable to query map {} - does it have a state file?'.format(section))
                        continue
                    data = q.query(section, start_time)
                    for item in data["data"]:
                        log.info(pprint.pformat(item))
                    state.update_ts(data["max_date_str"])

            if self.config.getboolean('main', 'debug'):
                log.info("Only sleeping a short while as debug mode is on")
                log.info('================================================================================')
                time.sleep(30)
            else:
                log.info('================================================================================')
                time.sleep(3600)


if __name__ == '__main__':
    main = Main()
    main.main()
