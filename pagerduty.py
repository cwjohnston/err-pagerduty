from errbot import BotPlugin, botcmd
from errbot.utils import get_sender_username
from operator import itemgetter
from urllib2 import HTTPError
from datetime import datetime, timedelta
import logging
import pygerduty
import requests
import json


class PagerDuty(BotPlugin):
    """An Err plugin for interacting with PagerDuty"""
    min_err_version = '1.6.0'  # Optional, but recommended
    max_err_version = '2.0.0'  # Optional, but recommended

    def configure(self, configuration):
        super(PagerDuty, self).configure(configuration)
        if configuration and ('SUBDOMAIN' in configuration and 'API_KEY' in configuration):
            self.pager = pygerduty.PagerDuty(self.config['SUBDOMAIN'], self.config['API_KEY'])

    def get_configuration_template(self):
        return {'SUBDOMAIN': "myorg",
                'API_KEY': "secret",
                'SERVICE_API_KEY': "secret",
                'SCHEDULE_ID': "someschedule"}

    def get_triggered_incidents(self):
        triggered_incidents = self.pager.incidents.list(status='triggered')
        logging.debug("[PagerDuty] Found %s triggered incidents" % (len(triggered_incidents),))
        return triggered_incidents

    def get_acknowledged_incidents(self):
        acknowledged_incidents = self.pager.incidents.list(status='acknowledged')
        logging.debug("[PagerDuty] Found %s acknowledged incidents" % (len(acknowledged_incidents),))
        return acknowledged_incidents

    def get_active_incidents(self):
        active_incidents = []
        active_incidents.extend(self.get_triggered_incidents())
        active_incidents.extend(self.get_acknowledged_incidents())
        logging.debug("[PagerDuty] Found %s active incidents" % (len(active_incidents),))
        return active_incidents

    def get_incident(self, incident_id):
        incident = self.pager.incidents.show(id=incident_id)
        return incident

    def get_incident_id_by_incident_key(self, incident_key):
        pass

    def get_pd_id_by_email(self, email):
        users = self.pager.users.list()
        for user in users:
            if user.email == email:
                return user.id

    def get_users(self):
        return self.get('pagerduty_users', [])

    def get_user(self, uid):
        users = self.get_users()
        user_index = map(itemgetter('uid'), users).index(uid)
        user = users[user_index]
        return user

    def add_user(self, **kwargs):
        users = self.get_users()
        users.append({'uid': kwargs['uid'], 'email': kwargs['email'], 'pd_id': kwargs['pd_id']})
        self['pagerduty_users'] = users
        return True

    def remove_user(self, **kwargs):
        users = self.get_users()
        for user in users:
            if user['uid'] == kwargs['uid']:
                user_index = map(itemgetter('uid'), users).index(kwargs['uid'])
                del users[user_index]
                self['pagerduty_users'] = users
                return True

    def get_oncall_pd_id(self, schedule_id):
        now = datetime.now()
        onehour = now + timedelta(hours=1)
        query = {'since': now, 'until': onehour, 'overflow': False}

        try:
            response = self.pager.request('GET', '/api/v1/schedules/%s/entries' % (schedule_id,), query)
            return response['entries'][0]['user']['id']
        except HTTPError as e:
            logging.error("[PagerDuty] Error querying schedule entries for %s: %s" % (schedule_id, e,))
            raise Exception("Error querying schedule entries for %s: %s" % (schedule_id, e,))

    @botcmd(split_args_with=None)
    def pager_listusers(self, mess, args):
        """ List PagerDuty users registered with the bot """
        if self.config:
            users = self.get_users()
            return users
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_whoami(self, mess, args):
        """ ... and how did I get here?"""
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                uid = get_sender_username(mess)
                users = self.get_users()
                try:
                    user_index = map(itemgetter('uid'), users).index(uid)
                    user = users[user_index]
                    return "I have you registered as %s with PagerDuty ID %s" % (user['email'], user['pd_id'],)
                except ValueError as e:
                    return "I don't think I know you: %s" % (e,)
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_register(self, mess, args):
        """ Register as a PagerDuty user with the bot via your email address """
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                if len(args) <= 0:
                    return "I can't register you without an email address"
                else:
                    users = self.get_users()
                    uid = get_sender_username(mess)
                    email = args[0]

                    try:
                        user_index = map(itemgetter('uid'), users).index(uid)
                        user = users[user_index]
                        return "You are already registered as %s" % (user['email'],)
                    except:
                        try:
                            existing_user_index = map(itemgetter('email'), users).index(email)
                            existing_user = users[existing_user_index]
                            return "The email address you provided is already registered to %s" % (existing_user['uid'],)
                        except:
                            pd_id = self.get_pd_id_by_email(email)

                            if pd_id is None:
                                return "Sorry, I couldn't find a PagerDuty user with that email address"
                            else:
                                logging.info("[PagerDuty] registering user ID %s as %s" % (uid, email,))
                                self.add_user(uid=uid, email=email, pd_id=pd_id)
                                updated_user_list = self.get_users()
                                logging.debug("[PagerDuty] new user list: %s" % (updated_user_list,))
                                return "You are now licensed to kill"
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_unregister(self, mess, args):
        """ Remove your PagerDuty user registration """
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                users = self.get_users()
                uid = get_sender_username(mess)
                for user in users:
                    if user['uid'] == uid:
                        logging.info("[PagerDuty] unregistering user ID %s" % (uid,))
                        self.remove_user(uid=uid)
                        updated_user_list = self.get_users()
                        logging.debug("[PagerDuty] new user list: %s" % (updated_user_list,))
                        return "You're dead to me"
                else:
                    return "Sorry, I'm afraid I don't know who you are to begin with"
        else:
                return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_oncall(self, mess, args):
        """ Find out who has the pager """
        if self.config:
            try:
                oncall_pd_id = self.get_oncall_pd_id(self.config['SCHEDULE_ID'])
                users = self.get_users()
                oncall_index = map(itemgetter('pd_id'), users).index(oncall_pd_id)
                oncall_user = users[oncall_index]
                return "%s has the pager" % (oncall_user['uid'])
            except Exception, e:
                return "Sorry, I couldn't figure out who is on call currently: %s" % (e,)
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def oncall(self, mess, args):
        """ Find out who has the pager """
        return self.pager_oncall(mess, args)

    @botcmd(split_args_with=None)
    def pager_list(self, mess, args):
        """ List acknowledged and triggered incidents """
        if self.config:
            incidents = self.get_active_incidents()
            return "found %s active incidents: %s" % (len(incidents), incidents,)
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_summarize(self, mess, args):
        """ Not yet implemented """
        pass

    @botcmd(split_args_with=None)
    def pager_show(self, mess, args):
        """ Not yet implemented """
        pass

    @botcmd(split_args_with=None)
    def pager_trigger(self, mess, args):
        """ Trigger an incident """
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                pd_api = "https://events.pagerduty.com/generic/2010-04-15/create_event.json"
                body = {'service_key': self.config['SERVICE_API_KEY'],
                        'event_type': 'trigger',
                        'description': 'Urgent page via chat',
                        'details': {'requestor': get_sender_username(mess),
                                    'message': " ".join(args)}
                        }

                response = requests.post(pd_api, data=json.dumps(body))
                if response.status_code in (200,):
                    return "Triggered incident %s" % (response.json()['incident_key'],)
                else:
                    logging.error("[PagerDuty] Non-200 response: %s" % response.status_code)
                    logging.error("[PagerDuty] Body: %s" % response.json())
                    return "Sorry, something went wrong. You should check the logs."
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_ack(self, mess, args):
        """ Acknowledge an incident by it's alphanumeric ID """
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                try:
                    requestor = self.get_user(get_sender_username(mess))
                except:
                    return "Sorry, I don't know who you are. Please use !pager register to teach me your email address."

                try:
                    incident_id = args[0]
                    logging.info("[PagerDuty] acknowledging incident %s by request of %s" % (incident_id, requestor['uid']))
                    self.pager.incidents.update(requestor['pd_id'], {'id': incident_id, 'status': 'acknowledged'})
                    return "Acknowledged incident %s" % (incident_id,)
                except HTTPError as e:
                    logging.error("[PagerDuty] Error acknowledging incident %s: %s" % (incident_id, e,))
                    return "Failed to acknowledge incident %s: %s" % (incident_id, e,)
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_resolve(self, mess, args):
        """ Resolve an incident by it's alphanumeric ID """
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                try:
                    requestor = self.get_user(get_sender_username(mess))
                except:
                    return "Sorry, I don't know who you are. Please use !pager register to teach me your email address."
                try:
                    incident_id = args[0]
                    logging.info("[PagerDuty] resolving incident %s by request of %s" % (incident_id, requestor['uid']))
                    self.pager.incidents.update(requestor['pd_id'], {'id': incident_id, 'status': 'resolved'})
                    return "Resolved incident %s" % (incident_id,)
                except HTTPError as e:
                    logging.error("[PagerDuty] Error resolving incident %s: %s" % (incident_id, e,))
                    return "Failed to resolve incident %s: %s" % (incident_id, e,)
        else:
            return "Sorry, PagerDuty is not configured"

    @botcmd(split_args_with=None)
    def pager_steal(self, mess, args):
        """ Steal the pager for N minutes """
        if self.config:
            if mess.getType() == "chat":
                return "Sorry, you need to use group chat for PagerDuty commands"
            else:
                if len(args) <= 0:
                    return "Sorry, you need to specify the number of hours for which you'd like to steal the pager"
                else:
                    requestor_name = get_sender_username(mess)
                    users = self.get_users()
                    requestor_index = map(itemgetter('uid'), users).index(requestor_name)
                    requestor = users[requestor_index]
                    schedule_id = self.config['SCHEDULE_ID']

                    logging.info("[PagerDuty] override requestor found: %s" % (requestor,))

                    try:
                        override_duration = int(args[0])
                    except:
                        return "Sorry, I could not transform %s into an integer"

                    if requestor['pd_id'] == self.get_oncall_pd_id(schedule_id):
                        return "Sorry, you are already on call"
                    else:
                        now = datetime.now()
                        later = now + timedelta(minutes=override_duration)
                        try:
                            schedule = self.pager.schedules.show(schedule_id)
                            schedule.overrides.create(start=now.isoformat(), end=later.isoformat(), user_id=requestor['pd_id'])
                            return "Rejoice ye oncall, %s has the pager for %s minutes(s)" % (requestor['uid'], override_duration,)
                        except HTTPError as e:
                            logging.error("[PagerDuty] Error overriding schedule %s: %s" % (schedule_id, e,))
                            raise Exception("Error overriding schedule %s: %s" % (schedule_id, e,))
        else:
            return "Sorry, PagerDuty is not configured"
