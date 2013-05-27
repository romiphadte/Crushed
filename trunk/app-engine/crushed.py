import cgi
import facebook
import jinja2
import json
import logging
import os
import urllib
import webapp2

from google.appengine.api import capabilities
from google.appengine.ext import ndb

from webapp2_extras import sessions

jinja_environment = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])

FACEBOOK_APP_ID = '385599044882630'
FACEBOOK_APP_SECRET = '610d0092e35e0b07614d2c70fd78ba17'

config = {}
config['webapp2_extras.sessions'] = dict(secret_key='')

#Functions
def addNotification(notif_type, value, user):
	user = User.get_by_id(str(user))
	user.notifications.append(repr({notif_type:value}))
	user.put()
	return

#Models
class User(ndb.Model):
	crushes = ndb.IntegerProperty(repeated=True)
	notifications = ndb.StringProperty(repeated=True)
	signuptime = ndb.DateTimeProperty(auto_now_add=True)
	interests = ndb.IntegerProperty(default=0) #0 = all, 1 = men, 2 = women

class BaseHandler(webapp2.RequestHandler):
	"""Provides access to the active Facebook user in self.current_user

	The property is lazy-loaded on first access, using the cookie saved
	by the Facebook JavaScript SDK to determine the user ID of the active
	user. See http://developers.facebook.com/docs/authentication/ for
	more information.
	"""
	@property
	def current_user(self):
		if self.session.get("user"):
			# User is logged in
			return self.session.get("user")
		else:
			# Either used just logged in or just saw the first page
			# We'll see here
			cookie = facebook.get_user_from_cookie(self.request.cookies,
												   FACEBOOK_APP_ID,
												   FACEBOOK_APP_SECRET)
			if cookie:
				# Okay so user logged in.
				# Now, check to see if existing user
				user = User.get_by_key_name(cookie["uid"])
				if not user:
					# Not an existing user so get user info
					graph = facebook.GraphAPI(cookie["access_token"])
					profile = graph.get_object("me")
					user = User(
						key_name=str(profile["id"]),
						id=str(profile["id"]),
						name=profile["name"],
						profile_url=profile["link"],
						access_token=cookie["access_token"]
					)
					user.put()
				elif user.access_token != cookie["access_token"]:
					user.access_token = cookie["access_token"]
					user.put()
				# User is now logged in
				self.session["user"] = dict(
					name=user.name,
					profile_url=user.profile_url,
					id=user.id,
					access_token=user.access_token
				)
				return self.session.get("user")
		return None

	def dispatch(self):
		"""
		This snippet of code is taken from the webapp2 framework documentation.
		See more at
		http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

		"""
		self.session_store = sessions.get_store(request=self.request)
		try:
			webapp2.RequestHandler.dispatch(self)
		finally:
			self.session_store.save_sessions(self.response)

	@webapp2.cached_property
	def session(self):
		"""
		This snippet of code is taken from the webapp2 framework documentation.
		See more at
		http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

		"""
		return self.session_store.get_session()

#API system
class MainPage(BaseHandler):
	def get(self):
		template_values = {}
		template = jinja_environment.get_template('templates/index.html')
		self.response.out.write(template.render(template_values))
	def post(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.out.write('This is the Crushed. Access the API at /api if you really want to get information.')

class APIHandler(webapp2.RequestHandler):
	def get(self):
		requesttype = self.request.get('requesttype')
		if requesttype == u'1': #Add Crush
			activeUserID = self.request.get('activeUserID')
			addingUserID = self.request.get('addingUserID')
			newAccount = False
			if not activeUserID or not addingUserID:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'Missing values.'}))
				self.response.set_status(400)
				return
			activeUserNDB = User.get_by_id(str(activeUserID))
			if not activeUserNDB:
				activeUserNDB = User(id=str(activeUserID),
									 crushes=[int(addingUserID)])
				activeUserNDB.put()
				newAccount = True
			elif int(addingUserID) in activeUserNDB.crushes and not newAccount:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'Crush already added.'}))
				self.response.set_status(400)
				return
			else:
				activeUserNDB.crushes.append(int(addingUserID))
				activeUserNDB.put()
			addingUserNDB = User.get_by_id(str(addingUserID))
			if addingUserNDB:
				if int(activeUserID) in addingUserNDB.crushes:
					addNotification('Crush', int(activeUserID), int(addingUserID))
					self.response.headers['Content-Type'] = 'application/json'
					self.response.out.write(json.dumps({'Success':'Crush added.','Reciprocation':True,'Crush Signed Up':True}))
					return
				else:
					addNotification('Crush', 'Someone', addingUserID)
					self.response.headers['Content-Type'] = 'application/json'
					self.response.out.write(json.dumps({'Success':'Crush added.','Reciprocation':False,'Crush Signed Up':True}))
					return
			else:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Success':'Crush added.','Reciprocation':False,'Crush Signed Up':False}))
				return
		elif requesttype == u'2': #Check notifs
			activeUserID = self.request.get('activeUserID')
			if not activeUserID:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'Missing values.'}))
				self.response.set_status(400)
				return
			activeUserNDB = User.get_by_id(str(activeUserID))
			if not activeUserNDB:
				activeUserNDB = User(id=str(activeUserID),
									 crushes=[],
									 notifications=[])
				activeUserNDB.put()
			self.response.headers['Content-Type'] = 'application/json'
			self.response.out.write(json.dumps(activeUserNDB.notifications))
			activeUserNDB.notifications = []
			activeUserNDB.put()
			return
		elif requesttype == u'3': #Get crushes
			activeUserID = self.request.get('activeUserID')
			if not activeUserID:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'Missing values.'}))
				self.response.set_status(400)
				return
			activeUserNDB = User.get_by_id(str(activeUserID))
			if not activeUserNDB:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'User does not exist.'}))
				self.response.set_status(400)
				return
			self.response.headers['Content-Type'] = 'application/json'
			self.response.out.write(json.dumps(activeUserNDB.crushes))
			return
		elif requesttype == u'4': #Get mutual crushes
			logging.debug(requesttype)
			logging.debug(self.request.get('activeUserID'))
			logging.debug(self.request)
			activeUserID = self.request.get('activeUserID')
			if not activeUserID:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'Missing values.'}))
				self.response.set_status(400)
				return
			activeUserNDB = User.get_by_id(str(activeUserID))
			if not activeUserNDB:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'User does not exist.'}))
				self.response.set_status(400)
				return
			mutualCrushes = []
			for crush in activeUserNDB.crushes:
				activeCrushNDB = User.get_by_id(str(crush))
				try:
					if int(activeUserID) in activeCrushNDB.crushes and crush not in mutualCrushes:
						mutualCrushes.append(crush)
				except:
					pass
			self.response.headers['Content-Type'] = 'application/json'
			self.response.out.write(", ".join(str(x) for x in mutualCrushes))
			return
		elif requesttype == u'5': #Get interests
			activeUserID = self.request.get('activeUserID')
			if not activeUserID:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'Missing values.'}))
				self.response.set_status(400)
				return
			activeUserNDB = User.get_by_id(str(activeUserID))
			if not activeUserNDB:
				self.response.headers['Content-Type'] = 'application/json'
				self.response.out.write(json.dumps({'Error':'User does not exist.'}))
				self.response.set_status(400)
				return
			self.response.headers['Content-Type'] = 'application/json'
			self.response.out.write(json.dumps({'Interests':str(activeUserNDB.interests)}))
			return
		else:
			self.error(404)
			return

class DevelopmentPageHandler(BaseHandler):
	def get(self):
		template = jinja_environment.get_template('templates/facebooktest.html')
		self.response.out.write(template.render(dict(
			facebook_app_id=FACEBOOK_APP_ID,
			current_user=self.current_user
		)))

	def post(self):
		url = self.request.get('url')
		file = urllib2.urlopen(url)
		graph = facebook.GraphAPI(self.current_user['access_token'])
		response = graph.put_photo(file, "Test Image")
		photo_url = ("http://www.facebook.com/"
					 "photo.php?fbid={0}".format(response['id']))
		self.redirect(str(photo_url))

app = webapp2.WSGIApplication([
	('/', MainPage),
	('/api', APIHandler),
	('/dev', DevelopmentPageHandler)
], debug=True, config=config)