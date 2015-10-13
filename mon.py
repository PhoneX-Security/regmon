#!/usr/bin/env python2
'''
Creates a new (or updates an existing) source phrase revision. Uploads current source language to the database.

PyMySQL needs to be installed.
$ pip install PyMySQL
$ pip install SQLAlchemy

@author Ph4r05
'''
import calendar
import calendar
import time
import subprocess
from time import sleep
import re

import commons
from commons import TranslateHelper
import pymysql
import pymysql.cursors
from tr_base import TRBase

from daemon import Daemon
import os
import sys
import argparse
import traceback
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from commons import Base, SourceFile, SourcePhrases, Translation

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

    def __str__(self):
        return "RegRecord::\"%s\", expires: \"%s\", callid: \"%s\", ua: \"%s\", cseq: \"%s\"" % (self.contact, self.expires, self.callid, self.userAgent, self.cseq)
    def __repr__(self):
        return str(self)

class AOR(object):
    '''
    Group object representing all registrations for given user.
    '''
    user = None
    contacts = []

    def __str__(self):
        return "AOR::\"%s\", contacts: %s" % (self.user, ";\n ".join([str(x) for x in self.contacts]))
    def __repr__(self):
        return str(self)

class Main(Daemon):
    connection = None
    engine = None
    session = None

    sampleInterval = 20
    isRunning = True
    lastActionTime = 0

    dbEntries = None
    dbKeys = None

    def connect(self):
        # load DB data from JSON configuration file.
        dbData = TranslateHelper.loadDbData()

        # Connect to the database
        self.connection = pymysql.connect(host=dbData['server'],
                                     user=dbData['user'],
                                     passwd=dbData['passwd'],
                                     db=dbData['db'],
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor)

        self.engine = create_engine(TranslateHelper.getConnectionString())
        # Bind the engine to the metadata of the Base class so that the
        # declaratives can be accessed through a DBSession instance
        Base.metadata.bind = self.engine
        DBSession = sessionmaker(bind=self.engine)
        self.session = DBSession()
    pass

    def utc(self):
        return calendar.timegm(time.gmtime())

    def regdump(self):
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
                    if curContact is not None and curAOR is not None:
                        curAOR.contacts.append(curContact)
                    aorDict[lastUser] = curAOR

                curAOR = AOR()
                curContact = ContactRecord()
                lastUser = ldata.split("AOR::")[1].strip()
                curAOR.user = lastUser

            elif ldata.startswith("Contact::"):
                # New registration, close current user, registration.
                if curContact is not None and curAOR is not None:
                    curAOR.contacts.append(curContact)
                curContact = ContactRecord()

                # Parse new record.
                contact = ldata.split("Contact::")[1].strip()
                m = re.match(r"^(\w+):([\w\-]+)@([\w\.]+):([\d]+);(.*)$", contact)
                if m:
                    ct = Contact(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
                    curContact.contact = ct
                    print("Contact: %s" % contact)

                else:
                    print("Regex matching failed: %s" % contact)

            elif ldata.startswith("Expires::"):
                expires = ldata.split("Expires::")[1].strip()
                curContact.expires = expires

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
        if curContact is not None and curAOR is not None:
            curAOR.contacts.append(curContact)
            aorDict[curAOR.user] = curAOR

        print aorDict

    def run(self):

        # Start simple sampling.
        while self.isRunning:
            cUtc = self.utc()
            if (self.lastActionTime + self.sampleInterval >= cUtc):
                sleep(0.5)
                continue

            self.lastActionTime = cUtc

            # Execute opensipsctl ul show to get current registration dump.
            self.regdump()
            continue

            # Connect to the database again and insert new records.
            self.connect()

            # self.dbEntries = self.loadAllSourcePhrasesForRevision(self.lang)
            # self.dbKeys = dict((x.stringKey, x) for x in self.dbEntries)
            #
            # stringCtr = 0
            # for xml in TranslateHelper.genLanguageFiles(self.app, self.lang):
            #     entries = TranslateHelper.getStringEntries(xml, stringCtr)
            #     stringCtr += len(entries)
            #
            #     if len(entries) == 0:
            #         continue
            #
            #     baseName = os.path.basename(xml)
            #     fileData = None
            #     with open (xml, "r") as myfile:
            #         fileData = myfile.read().replace('\n', '')
            #
            #     sfile = self.updateSourceFile(baseName, fileData, self.lang)
            #
            #     # Update Db string entries.
            #     for entry in entries:
            #         self.updateSourcePhrase(entries[entry], sfile, self.lang)
            #     self.session.commit()

# Main executable code
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenSips registration monitor script', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--app',            help='', default='.', required=False)
    parser.add_argument('--opensips',       help='', default='en', required=False)
    parser.add_argument('--run',            help='', default=0, type=int, required=False)
    args = parser.parse_args()

    m = Main('/var/run/sipregmon.pid')
    m.app = args.app

    if args.run > 0:
        print("Going to start without daemonizing")
        m.run()
    else:
        m.start()
