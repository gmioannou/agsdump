import requests
import json

from arcgis import ArcGIS

class MapService(ArcGIS):
    def __init__(self, url):
        ArcGIS.__init__(self, url)

    @property
    def descriptor(self):
        params = {'f': 'json'}
        response = requests.get(self.url, params=params)
        return json.loads(response.text)

    @property
    def layers(self):
        return self.descriptor.get('layers')