#!/usr/bin/env python2
'''
Creates a new (or updates an existing) source phrase revision. Uploads current source language to the database.

PyMySQL needs to be installed.
$ pip install PyMySQL
$ pip install SQLAlchemy

@author Ph4r05
'''
import calendar
import time
import subprocess
from time import sleep
import re

import commons
import numbers
import pymysql
import pymysql.cursors

from daemon import Daemon
import os
import sys
import argparse
import traceback
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from commons import Base
from commons import SipRegMon
from commons import DbHelper

class Contact(object):
    '''
    Represents parsed user contact.
    '''
    scheme = None
    user = None
    host = None
    port = None
    extra = None

    def __str__(self):
        return "<Contact> scheme: \"%s\", user: \"%s\", host:\"%s\", port: \"%d\", extra:\"%s\"" % (self.scheme, self.user, self.host, self.port, self.extra)
    def __repr__(self):
        return str(self)

    def __init__(self, aScheme, aUser, aHost, aPort, aExtra):
        self.scheme = aScheme
        self.user = aUser
        self.host = aHost
        self.port = int(aPort)
        self.extra = aExtra

class ContactRecord(object):
    '''
    One instance represents one registration record.
    '''
    contact = None
    expires = None
    callid = None
    userAgent = None
    cseq = None
    socket = None

    def __str__(self):
        return "RegRecord::\"%s\", expires: \"%s\", callid: \"%s\", ua: \"%s\", cseq: \"%s\", socket: \"%s\"" \
               % (self.contact, self.expires, self.callid, self.userAgent, self.cseq, self.socket)
    def __repr__(self):
        return str(self)

class AOR(object):
    '''
    Group object representing all registrations for given user.
    '''
    user = None
    contacts = list([])

    def __init__(self):
        self.contacts = list([])
    def __str__(self):
        return "AOR::\"%s\", contacts: %s" % (self.user, ";\n ".join([str(x) for x in self.contacts]))
    def __repr__(self):
        return str(self)

class Socket(object):
    ip1 = None
    ip2 = None
    state = None
    proc = None
    timer = None

    def __str__(self):
        return "%s -> %s, state: %s, proc: %s, timer: %s" % (self.ip1, self.ip2, self.state, self.proc, self.timer)
    def __repr__(self):
        return str(self)

class Main(Daemon):
    connection = None
    engine = None
    session = None

    sampleInterval = 20
    isRunning = True
    lastActionTime = 0

    runOnly = False
    wantedNames = None
    regNum = -1

    def connect(self):
        # load DB data from JSON configuration file.
        dbData = DbHelper.loadDbData()

        # Connect to the database
        self.connection = pymysql.connect(host=dbData['server'],
                                     user=dbData['user'],
                                     passwd=dbData['passwd'],
                                     db=dbData['db'],
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor)

        self.engine = create_engine(DbHelper.getConnectionString())
        # Bind the engine to the metadata of the Base class so that the
        # declaratives can be accessed through a DBSession instance
        Base.metadata.bind = self.engine
        DBSession = sessionmaker(bind=self.engine)
        self.session = DBSession()

    def utc(self):
        return calendar.timegm(time.gmtime())

    def sockdump(self):
        cmd = ['netstat -tunpo']
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()

        # Wait for date to terminate. Get return returncode
        p_status = p.wait()

        # Line by line processing of the output.
        lines = out.splitlines()
        connections = {}

        for line in lines:
            ldata = line.strip()
            m = re.match(r"^(\w+)[\s\t]+([\d]+)[\s\t]+([\d]+)[\s\t]+([\w:\.\*]+)[\s\t]+([\w:\*\.]+)[\s\t]+([\w:\.\*/]+)[\s\t]+([\w:\.\*/]+)[\s\t]+(.+)$", ldata)
            if m:
                sock = Socket()
                sock.ip1 = m.group(4)
                sock.ip2 = m.group(5)
                sock.state = m.group(6)
                sock.proc = m.group(7)
                sock.timer = m.group(8)
                if not (":5061" in sock.ip1):
                    continue
                connections[sock.ip2] = sock

        return connections

    def fillMatchingConnection(self, contactRecord, connections):
        if contactRecord is None or contactRecord.contact is None:
            return None
        if connections is None:
            return contactRecord
        con = "%s:%s" % (contactRecord.contact.host, contactRecord.contact.port)
        if con in connections:
            contactRecord.socket = connections[con]
        return contactRecord

    def regdump(self, connections):
        cmd = ['/usr/sbin/opensipsctl ul show']
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()

        # Wait for date to terminate. Get return returncode
        p_status = p.wait()

        # Line by line processing of the output.
        lines = out.splitlines()

        # Line by line processing of the registration data.
        lastUser = None
        curContact = None
        curAOR = None
        aors = []
        aorDict = {}

        for line in lines:
            ldata = line.strip()

            if ldata.startswith("AOR::"):
                # Close current user.
                if lastUser is not None:
                    if curContact is not None and curAOR is not None and curContact.contact is not None:
                        self.fillMatchingConnection(curContact, connections)
                        curAOR.contacts.append(curContact)
                    aorDict[lastUser] = curAOR

                curAOR = AOR()
                curContact = ContactRecord()
                lastUser = ldata.split("AOR::")[1].strip()
                curAOR.user = lastUser

            elif ldata.startswith("Contact::"):
                # New registration, close current user, registration.
                if curContact is not None and curAOR is not None and curContact.contact is not None:
                    self.fillMatchingConnection(curContact, connections)
                    curAOR.contacts.append(curContact)
                curContact = ContactRecord()

                # Parse new record.
                contact = ldata.split("Contact::")[1].strip()
                m = re.match(r"^(\w+):([\w\-]+)@([\w\.]+):([\d]+);(.*)$", contact)
                if m:
                    ct = Contact(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
                    curContact.contact = ct

                else:
                    print("Regex matching failed: %s" % contact)

            elif ldata.startswith("Expires::"):
                expires = ldata.split("Expires::")[1].strip()
                try:
                    curContact.expires = int(expires)
                except:
                    curContact.expires = -1

            elif ldata.startswith("Callid::"):
                callId = ldata.split("Callid::")[1].strip()
                curContact.callid = callId

            elif ldata.startswith("Cseq::"):
                cseq = ldata.split("Cseq::")[1].strip()
                curContact.cseq = cseq

            elif ldata.startswith("User-agent::"):
                ua = ldata.split("User-agent::")[1].strip()
                curContact.userAgent = ua

        # Dump current contact.
        if curContact is not None and curAOR is not None and curContact.contact is not None:
            curAOR.contacts.append(curContact)
            aorDict[curAOR.user] = curAOR

        return aorDict

    def isContactWanted(self, name):
        if self.wantedNames is None or len(self.wantedNames) == 0:
            return True
        for cname in self.wantedNames:
            if cname in name:
                return True
        return False

    def run(self):

        # Start simple sampling.
        while self.isRunning:
            cUtc = self.utc()
            if (self.lastActionTime + self.sampleInterval > cUtc):
                sleep(0.3)
                continue

            self.lastActionTime = cUtc

            try:
                # Execute opensipsctl ul show to get current registration dump.
                connections = self.sockdump()
                aorDict = self.regdump(connections)

                # Connect to the database again and insert new records.
                self.connect()

                # For dumping
                dbRecs = []

                # Insert entry to the database.
                for ukey in aorDict:
                    aor = aorDict[ukey]
                    if aor.contacts is None or len(aor.contacts) == 0:
                        continue
                    if not self.isContactWanted(aor.user):
                        continue

                    for (idx,contactRecord) in enumerate(aor.contacts):
                        if self.regNum >= 0 and idx >= self.regNum:
                            continue

                        en = SipRegMon()
                        en.sip = aor.user
                        en.num_registrations = len(aor.contacts)
                        en.ip_addr = contactRecord.contact.host
                        en.port = int(contactRecord.contact.port)
                        en.cseq = contactRecord.cseq
                        en.expires = contactRecord.expires
                        en.reg_idx = idx

                        if contactRecord.socket is None:
                            en.sock_state = None
                            en.ka_timer = None
                        else:
                            en.sock_state = contactRecord.socket.state
                            en.ka_timer = contactRecord.socket.timer

                        if not self.runOnly:
                            self.session.add(en)
                        else:
                            dbRecs.append(en)

                if self.runOnly:
                    dbRecs.sort(key=lambda x: x.sip)
                    print("="*80)
                    print("Dump time: " + str(datetime.datetime.now()))

                    for en in dbRecs:
                        print("AOR: %s\n\t%s:%s\n\texpire: %s\n\tcseq: %s\n\tidx:%s/%s\n\tsocket: %s  timer: %s\n" %
                                  (en.sip, en.ip_addr, en.port, en.expires, en.cseq, en.reg_idx, en.num_registrations,
                                   en.sock_state, en.ka_timer))

            except Exception as inst:
                print traceback.format_exc()
                print "Exception", inst

            finally:
                try:
                    self.session.commit()
                except Exception as inst:
                    print traceback.format_exc()
                    print "Exception", inst

# Main executable code
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenSips registration monitor script', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--app',            help='', default='.', required=False)
    parser.add_argument('--opensips',       help='', default='en', required=False)
    parser.add_argument('--run',            help='Run only, no deamon mode, no DB storage', default=0, type=int, required=False)
    parser.add_argument('--interval',       help='Sampling interval', default=20, type=int, required=False)
    parser.add_argument('--wanted',         help='List of wanted user names', default=None, required=False)
    parser.add_argument('--regnum',         help='Number of registrations to track at max', default=-1, type=int, required=False)
    args = parser.parse_args()

    m = Main('/var/run/sipregmon/pid.pid', stderr="/var/log/sipregmon/err.log", stdout="/var/log/sipregmon/out.log")
    m.app = args.app
    m.verbose = 3
    m.sampleInterval = args.interval
    m.runOnly = args.run > 0
    m.regNum = args.regnum

    if args.wanted is not None:
        wantedStr = args.wanted
        m.wantedNames = [x.strip() for x in wantedStr.split(",")]

    if args.run > 0:
        print("Going to start without daemonizing")
        m.run()
    else:
        m.start()
