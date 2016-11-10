from weppy import response, AppModule
from weppy.handlers import RequirePipe

from starter_weppy import app, db, auth
from ..controller_utils import not_auth

user = AppModule(app, 'user', __name__, template_folder="user")
user.pipeline = [RequirePipe(auth.is_logged_in, not_auth)]


@user.route("/user/<str:userid>")
def profile(userid):
    user_row = db.User(id=userid)
    response.meta.title = "StarterWeppy | " + user_row.first_name + " " + \
                          user_row.last_name + " profile"
    return dict(user=user_row)
