from weppy import AppModule
from weppy.tools import ServicePipe
from starter_weppy import app

api = AppModule(app, 'api', __name__, url_prefix='api')
api.pipeline = [ServicePipe('json')]


@api.route()
def version():
    json = {
        'version': 'v1'
    }
    return dict(status='OK', data=json)
