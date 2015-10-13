#!/usr/bin/env python2
'''
Dependencies:
$ pip install PyMySQL
$ pip install SQLAlchemy

@author Ph4r05
'''

import sys
import os
import json
from pprint import pprint
import traceback
from sqlalchemy import Column, DateTime, String, Integer, ForeignKey, func, Enum, Text, TIMESTAMP, text
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
class SipRegMon(Base):
    '''
    DB Entity for source file record.
    '''
    __tablename__ = 'phx_reg_mon'
    id = Column(Integer, primary_key=True)
    sip = Column(String(128))
    ip_addr = Column(String(24))
    port = Column(Integer)
    expires = Column(Integer)
    cseq = Column(Integer)
    reg_idx = Column(Integer)
    sock_state = Column(String(24), nullable=True)
    ka_timer = Column(String(64), nullable=True)
    created_at = Column(TIMESTAMP, server_onupdate=text('CURRENT_TIMESTAMP'))
    num_registrations = Column(Integer)

class DbHelper(object):
    @staticmethod
    def loadDbData():
        '''
        Loads DB configuration data (address, username, password, database) from JSON file, returns a dictionary.
        :return:
        '''
        filename = os.path.dirname(os.path.realpath(__file__))+"/db.json"
        if not os.path.exists(filename):
            print "[!] Error: DB config was not found: %s" % filename
            sys.exit(1)
        with open(filename) as data_file:
            data = json.load(data_file)
            return data

    @staticmethod
    def getConnectionString():
        dbData = DbHelper.loadDbData()
        return 'mysql+pymysql://%s:%s@%s/%s?charset=utf8' % (dbData['user'], dbData['passwd'], dbData['server'], dbData['db'])
        pass
