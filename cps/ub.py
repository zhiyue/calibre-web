#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2012-2019 mutschler, jkrehm, cervinko, janeczku, OzzieIsaacs, csitko
#                            ok11, issmirnov, idalin
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

from __future__ import division, print_function, unicode_literals
import os
import datetime
from binascii import hexlify

from flask import g
from flask_babel import gettext as _
from flask_login import AnonymousUserMixin
from werkzeug.local import LocalProxy
try:
    from flask_dance.consumer.backend.sqla import OAuthConsumerMixin
    oauth_support = True
except ImportError:
    oauth_support = False
from sqlalchemy import create_engine, exc, exists
from sqlalchemy import Column, ForeignKey
from sqlalchemy import String, Integer, SmallInteger, Boolean, DateTime
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash

from . import constants # , config


session = None
Base = declarative_base()


def get_sidebar_config(kwargs=None):
    kwargs = kwargs or []
    if 'content' in kwargs:
        content = kwargs['content']
        content = isinstance(content, (User,LocalProxy)) and not content.role_anonymous()
    else:
        content = 'conf' in kwargs
    sidebar = list()
    sidebar.append({"glyph": "glyphicon-book", "text": _('Recently Added'), "link": 'web.index', "id": "new",
                    "visibility": constants.SIDEBAR_RECENT, 'public': True, "page": "root",
                    "show_text": _('Show recent books'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-fire", "text": _('Hot Books'), "link": 'web.books_list', "id": "hot",
                    "visibility": constants.SIDEBAR_HOT, 'public': True, "page": "hot", "show_text": _('Show hot books'),
                    "config_show":True})
    sidebar.append(
        {"glyph": "glyphicon-star", "text": _('Best rated Books'), "link": 'web.books_list', "id": "rated",
         "visibility": constants.SIDEBAR_BEST_RATED, 'public': True, "page": "rated",
         "show_text": _('Show best rated books'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-eye-open", "text": _('Read Books'), "link": 'web.books_list', "id": "read",
                    "visibility": constants.SIDEBAR_READ_AND_UNREAD, 'public': (not g.user.is_anonymous), "page": "read",
                    "show_text": _('Show read and unread'), "config_show": content})
    sidebar.append(
        {"glyph": "glyphicon-eye-close", "text": _('Unread Books'), "link": 'web.books_list', "id": "unread",
         "visibility": constants.SIDEBAR_READ_AND_UNREAD, 'public': (not g.user.is_anonymous), "page": "unread",
         "show_text": _('Show unread'), "config_show":False})
    sidebar.append({"glyph": "glyphicon-random", "text": _('Discover'), "link": 'web.books_list', "id": "rand",
                    "visibility": constants.SIDEBAR_RANDOM, 'public': True, "page": "discover",
                    "show_text": _('Show random books'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-inbox", "text": _('Categories'), "link": 'web.category_list', "id": "cat",
                    "visibility": constants.SIDEBAR_CATEGORY, 'public': True, "page": "category",
                    "show_text": _('Show category selection'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-bookmark", "text": _('Series'), "link": 'web.series_list', "id": "serie",
                    "visibility": constants.SIDEBAR_SERIES, 'public': True, "page": "series",
                    "show_text": _('Show series selection'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-user", "text": _('Authors'), "link": 'web.author_list', "id": "author",
                    "visibility": constants.SIDEBAR_AUTHOR, 'public': True, "page": "author",
                    "show_text": _('Show author selection'), "config_show":True})
    sidebar.append(
        {"glyph": "glyphicon-text-size", "text": _('Publishers'), "link": 'web.publisher_list', "id": "publisher",
         "visibility": constants.SIDEBAR_PUBLISHER, 'public': True, "page": "publisher",
         "show_text": _('Show publisher selection'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-flag", "text": _('Languages'), "link": 'web.language_overview', "id": "lang",
                    "visibility": constants.SIDEBAR_LANGUAGE, 'public': (g.user.filter_language() == 'all'),
                    "page": "language",
                    "show_text": _('Show language selection'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-star-empty", "text": _('Ratings'), "link": 'web.ratings_list', "id": "rate",
                    "visibility": constants.SIDEBAR_RATING, 'public': True,
                    "page": "rating", "show_text": _('Show ratings selection'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-file", "text": _('File formats'), "link": 'web.formats_list', "id": "format",
                    "visibility": constants.SIDEBAR_FORMAT, 'public': True,
                    "page": "format", "show_text": _('Show file formats selection'), "config_show":True})
    return sidebar



class UserBase:

    @property
    def is_authenticated(self):
        return True

    def _has_role(self, role_flag):
        return constants.has_flag(self.role, role_flag)

    def role_admin(self):
        return self._has_role(constants.ROLE_ADMIN)

    def role_download(self):
        return self._has_role(constants.ROLE_DOWNLOAD)

    def role_upload(self):
        return self._has_role(constants.ROLE_UPLOAD)

    def role_edit(self):
        return self._has_role(constants.ROLE_EDIT)

    def role_passwd(self):
        return self._has_role(constants.ROLE_PASSWD)

    def role_anonymous(self):
        return self._has_role(constants.ROLE_ANONYMOUS)

    def role_edit_shelfs(self):
        return self._has_role(constants.ROLE_EDIT_SHELFS)

    def role_delete_books(self):
        return self._has_role(constants.ROLE_DELETE_BOOKS)

    def role_viewer(self):
        return self._has_role(constants.ROLE_VIEWER)

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return self.role_anonymous()

    def get_id(self):
        return str(self.id)

    def filter_language(self):
        return self.default_language

    def check_visibility(self, value):
        return constants.has_flag(self.sidebar_view, value)

    def show_detail_random(self):
        return self.check_visibility(constants.DETAIL_RANDOM)

    def __repr__(self):
        return '<User %r>' % self.nickname


# Baseclass for Users in Calibre-Web, settings which are depending on certain users are stored here. It is derived from
# User Base (all access methods are declared there)
class User(UserBase, Base):
    __tablename__ = 'user'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True)
    nickname = Column(String(64), unique=True)
    email = Column(String(120), unique=True, default="")
    role = Column(SmallInteger, default=constants.ROLE_USER)
    password = Column(String)
    kindle_mail = Column(String(120), default="")
    shelf = relationship('Shelf', backref='user', lazy='dynamic', order_by='Shelf.name')
    downloads = relationship('Downloads', backref='user', lazy='dynamic')
    locale = Column(String(2), default="en")
    sidebar_view = Column(Integer, default=1)
    default_language = Column(String(3), default="all")
    mature_content = Column(Boolean, default=True)


if oauth_support:
    class OAuth(OAuthConsumerMixin, Base):
        provider_user_id = Column(String(256))
        user_id = Column(Integer, ForeignKey(User.id))
        user = relationship(User)


class OAuthProvider(Base):
    __tablename__ = 'oauthProvider'

    id = Column(Integer, primary_key=True)
    provider_name = Column(String)
    oauth_client_id = Column(String)
    oauth_client_secret = Column(String)
    active = Column(Boolean)


# Class for anonymous user is derived from User base and completly overrides methods and properties for the
# anonymous user
class Anonymous(AnonymousUserMixin, UserBase):
    def __init__(self):
        self.loadSettings()

    def loadSettings(self):
        data = session.query(User).filter(User.role.op('&')(constants.ROLE_ANONYMOUS) == constants.ROLE_ANONYMOUS).first()  # type: User
        self.nickname = data.nickname
        self.role = data.role
        self.id=data.id
        self.sidebar_view = data.sidebar_view
        self.default_language = data.default_language
        self.locale = data.locale
        self.mature_content = data.mature_content
        self.kindle_mail = data.kindle_mail

        # settings = session.query(config).first()
        # self.anon_browse = settings.config_anonbrowse

    def role_admin(self):
        return False

    @property
    def is_active(self):
        return False

    @property
    def is_anonymous(self):
        return True # self.anon_browse

    @property
    def is_authenticated(self):
        return False


# Baseclass representing Shelfs in calibre-web in app.db
class Shelf(Base):
    __tablename__ = 'shelf'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    is_public = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey('user.id'))

    def __repr__(self):
        return '<Shelf %d:%r>' % (self.id, self.name)


# Baseclass representing Relationship between books and Shelfs in Calibre-Web in app.db (N:M)
class BookShelf(Base):
    __tablename__ = 'book_shelf_link'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer)
    order = Column(Integer)
    shelf = Column(Integer, ForeignKey('shelf.id'))

    def __repr__(self):
        return '<Book %r>' % self.id


class ReadBook(Base):
    __tablename__ = 'book_read_link'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, unique=False)
    user_id = Column(Integer, ForeignKey('user.id'), unique=False)
    is_read = Column(Boolean, unique=False)


class Bookmark(Base):
    __tablename__ = 'bookmark'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    book_id = Column(Integer)
    format = Column(String(collation='NOCASE'))
    bookmark_key = Column(String)


# Baseclass representing Downloads from calibre-web in app.db
class Downloads(Base):
    __tablename__ = 'downloads'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('user.id'))

    def __repr__(self):
        return '<Download %r' % self.book_id


# Baseclass representing allowed domains for registration
class Registration(Base):
    __tablename__ = 'registration'

    id = Column(Integer, primary_key=True)
    domain = Column(String)
    allow = Column(Integer)

    def __repr__(self):
        return u"<Registration('{0}')>".format(self.domain)



class RemoteAuthToken(Base):
    __tablename__ = 'remote_auth_token'

    id = Column(Integer, primary_key=True)
    auth_token = Column(String(8), unique=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    verified = Column(Boolean, default=False)
    expiration = Column(DateTime)

    def __init__(self):
        self.auth_token = (hexlify(os.urandom(4))).decode('utf-8')
        self.expiration = datetime.datetime.now() + datetime.timedelta(minutes=10)  # 10 min from now

    def __repr__(self):
        return '<Token %r>' % self.id


# Migrate database to current version, has to be updated after every database change. Currently migration from
# everywhere to curent should work. Migration is done by checking if relevant coloums are existing, and than adding
# rows with SQL commands
def migrate_Database(session):
    engine = session.bind
    if not engine.dialect.has_table(engine.connect(), "book_read_link"):
        ReadBook.__table__.create(bind=engine)
    if not engine.dialect.has_table(engine.connect(), "bookmark"):
        Bookmark.__table__.create(bind=engine)
    if not engine.dialect.has_table(engine.connect(), "registration"):
        ReadBook.__table__.create(bind=engine)
        conn = engine.connect()
        conn.execute("insert into registration (domain, allow) values('%.%',1)")
        session.commit()
    try:
        session.query(exists().where(Registration.allow)).scalar()
        session.commit()
    except exc.OperationalError:  # Database is not compatible, some columns are missing
        conn = engine.connect()
        conn.execute("ALTER TABLE registration ADD column 'allow' INTEGER")
        conn.execute("update registration set 'allow' = 1")
        session.commit()
    # Handle table exists, but no content
    cnt = session.query(Registration).count()
    if not cnt:
        conn = engine.connect()
        conn.execute("insert into registration (domain, allow) values('%.%',1)")
        session.commit()
    try:
        session.query(exists().where(BookShelf.order)).scalar()
    except exc.OperationalError:  # Database is not compatible, some columns are missing
        conn = engine.connect()
        conn.execute("ALTER TABLE book_shelf_link ADD column 'order' INTEGER DEFAULT 1")
        session.commit()
    try:
        create = False
        session.query(exists().where(User.sidebar_view)).scalar()
    except exc.OperationalError:  # Database is not compatible, some columns are missing
        conn = engine.connect()
        conn.execute("ALTER TABLE user ADD column `sidebar_view` Integer DEFAULT 1")
        session.commit()
        create = True
    try:
        if create:
            conn = engine.connect()
            conn.execute("SELECT language_books FROM user")
            session.commit()
    except exc.OperationalError:
        conn = engine.connect()
        conn.execute("UPDATE user SET 'sidebar_view' = (random_books* :side_random + language_books * :side_lang "
            "+ series_books * :side_series + category_books * :side_category + hot_books * "
            ":side_hot + :side_autor + :detail_random)"
            ,{'side_random': constants.SIDEBAR_RANDOM, 'side_lang': constants.SIDEBAR_LANGUAGE,
              'side_series': constants.SIDEBAR_SERIES,
            'side_category': constants.SIDEBAR_CATEGORY, 'side_hot': constants.SIDEBAR_HOT,
              'side_autor': constants.SIDEBAR_AUTHOR,
            'detail_random': constants.DETAIL_RANDOM})
        session.commit()
    try:
        session.query(exists().where(User.mature_content)).scalar()
    except exc.OperationalError:
        conn = engine.connect()
        conn.execute("ALTER TABLE user ADD column `mature_content` INTEGER DEFAULT 1")

    if session.query(User).filter(User.role.op('&')(constants.ROLE_ANONYMOUS) == constants.ROLE_ANONYMOUS).first() is None:
        create_anonymous_user(session)
    try:
        # check if one table with autoincrement is existing (should be user table)
        conn = engine.connect()
        conn.execute("SELECT COUNT(*) FROM sqlite_sequence WHERE name='user'")
    except exc.OperationalError:
        # Create new table user_id and copy contents of table user into it
        conn = engine.connect()
        conn.execute("CREATE TABLE user_id (id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
                            "nickname VARCHAR(64),"
                            "email VARCHAR(120),"
                            "role SMALLINT,"
                            "password VARCHAR,"
                            "kindle_mail VARCHAR(120),"
                            "locale VARCHAR(2),"
                            "sidebar_view INTEGER,"
                            "default_language VARCHAR(3),"
                            "mature_content BOOLEAN,"
                            "UNIQUE (nickname),"
                            "UNIQUE (email),"
                            "CHECK (mature_content IN (0, 1)))")
        conn.execute("INSERT INTO user_id(id, nickname, email, role, password, kindle_mail,locale,"
                        "sidebar_view, default_language, mature_content) "
                     "SELECT id, nickname, email, role, password, kindle_mail, locale,"
                        "sidebar_view, default_language, mature_content FROM user")
        # delete old user table and rename new user_id table to user:
        conn.execute("DROP TABLE user")
        conn.execute("ALTER TABLE user_id RENAME TO user")
        session.commit()

    # Remove login capability of user Guest
    conn = engine.connect()
    conn.execute("UPDATE user SET password='' where nickname = 'Guest' and password !=''")
    session.commit()


def clean_database(session):
    # Remove expired remote login tokens
    now = datetime.datetime.now()
    session.query(RemoteAuthToken).filter(now > RemoteAuthToken.expiration).delete()
    session.commit()


# Save downloaded books per user in calibre-web's own database
def update_download(book_id, user_id):
    check = session.query(Downloads).filter(Downloads.user_id == user_id).filter(Downloads.book_id ==
                                                                                          book_id).first()

    if not check:
        new_download = Downloads(user_id=user_id, book_id=book_id)
        session.add(new_download)
        session.commit()

# Delete non exisiting downloaded books in calibre-web's own database
def delete_download(book_id):
    session.query(Downloads).filter(book_id == Downloads.book_id).delete()
    session.commit()

# Generate user Guest (translated text), as anoymous user, no rights
def create_anonymous_user(session):
    user = User()
    user.nickname = "Guest"
    user.email = 'no@email'
    user.role = constants.ROLE_ANONYMOUS
    user.password = ''

    session.add(user)
    try:
        session.commit()
    except Exception as e:
        session.rollback()


# Generate User admin with admin123 password, and access to everything
def create_admin_user(session):
    user = User()
    user.nickname = "admin"
    user.role = constants.ADMIN_USER_ROLES
    user.sidebar_view = constants.ADMIN_USER_SIDEBAR

    user.password = generate_password_hash(constants.DEFAULT_PASSWORD)

    session.add(user)
    try:
        session.commit()
    except Exception:
        session.rollback()


def init_db(app_db_path):
    # Open session for database connection
    global session

    engine = create_engine(u'sqlite:///{0}'.format(app_db_path), echo=False)

    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()

    if os.path.exists(app_db_path):
        Base.metadata.create_all(engine)
        migrate_Database(session)
        clean_database(session)
    else:
        Base.metadata.create_all(engine)
        create_admin_user(session)
        create_anonymous_user(session)


def dispose():
    global session

    old_session = session
    session = None
    if old_session:
        try: old_session.close()
        except: pass
        if old_session.bind:
            try: old_session.bind.dispose()
            except: pass
